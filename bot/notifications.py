# bot/notifications.py
import os
import httpx
import logging
from datetime import date, timedelta
from telegram import Bot
from bot.DB import get_session, User
import datetime
from dotenv import load_dotenv

from database.moex_lookup import get_bond_coupons_from_moex

load_dotenv()
API_TOKEN = os.getenv("T_TOKEN")
BASE_URL_TINKOFF = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetBondCoupons"


async def get_bond_coupons_tinkoff(figi: str, from_date: datetime, to_date: datetime):
    """Получение информации о купонах облигации с API Tinkoff Invest."""
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }

    # Преобразуем объекты datetime в строку в формате ISO 8601 с временем
    params = {
        "instrumentId": figi,
        "from": from_date.isoformat(),  # Преобразуем datetime в строку
        "to": to_date.isoformat()  # Преобразуем datetime в строку
    }

    try:
        # Логирование запроса
        logging.info(f"🔄 Отправка запроса к Tinkoff API с параметрами: {params}")

        async with httpx.AsyncClient() as client:
            response = await client.post(BASE_URL_TINKOFF, headers=headers, json=params)
            response.raise_for_status()
            data = response.json()

            # Логирование ответа
            logging.info(f"📄 Ответ от Tinkoff API: {data}")

            return data.get("events", [])
    except httpx.RequestError as e:
        logging.error(f"❌ Ошибка при запросе к API T-Invest: {e}")
        return []


async def check_and_notify(bot: Bot):
    logging.info("🔄 Проверка уведомлений запущена...")
    today = date.today()
    notify_date = today + timedelta(days=3)

    session = get_session()
    users = session.query(User).all()

    for user in users:
        for bond in user.tracked_bonds:
            from_date = today.isoformat()
            to_date = (today + timedelta(days=4)).isoformat()

            # Пробуем получить купоны от Tinkoff
            events = await get_bond_coupons_tinkoff(bond.figi, from_date, to_date)

            # Если не получили ничего — используем MOEX как запасной план
            if not events:
                logging.info(f"🔁 Данные не найдены в T-Invest для {bond.figi}, пробуем МОЕКС.")
                events = await get_bond_coupons_from_moex(bond.isin)

            for event in events:
                # Унифицированная обработка событий из двух источников
                event_date = event.get("couponDate") or event.get("COUPONDATE")
                event_amount_units = event.get("payOneBond", {}).get("units")
                event_amount_nano = event.get("payOneBond", {}).get("nano")

                if event_date and event_amount_units is not None and event_amount_nano is not None:
                    event_date = date.fromisoformat(event_date.split("T")[0])

                    # Рассчитываем полную сумму купона (в рублях) с учетом units и nano
                    event_amount = int(event_amount_units) + int(event_amount_nano) / 1e9  # Переводим в рубли

                    # Обновление данных для следующего купона в БД
                    if event_date > today:  # Только для будущих событий
                        bond.next_coupon_date = event_date
                        bond.next_coupon_value = event_amount
                        session.commit()  # Сохраняем изменения в БД
                        logging.info(f"✅ Данные обновлены для облигации {bond.isin}: "
                                     f"next_coupon_date = {event_date}, next_coupon_value = {event_amount}")
                    elif event_date == notify_date:
                        text = (
                            f"🔔 Напоминание: через 3 дня ({event_date}) у бумаги {bond.isin} — событие: {event_type.upper()}.\n"
                            f"Сумма купона: {event_amount} руб."
                        )
                        try:
                            await bot.send_message(chat_id=user.tg_id, text=text)
                            logging.info(f"✅ Уведомление отправлено: {user.full_name} — {bond.isin}")
                        except Exception as e:
                            logging.error(f"❌ Не удалось отправить уведомление: {e}")
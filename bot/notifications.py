# bot/notifications.py
import os
import httpx
import logging
from datetime import date, timedelta
from telegram import Bot
from bot.database import get_session, User
from database.figi_lookup import get_figi_by_ticker_and_classcode
from database.moex_lookup import get_bond_coupons_from_moex
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("T_TOKEN")
BASE_URL_TINKOFF = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetBondCoupons"


async def get_bond_coupons_tinkoff(figi: str, from_date: str, to_date: str):
    """Получение информации о купонах облигации с API Tinkoff Invest."""
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    params = {
        "instrumentId": figi,
        "from": from_date,
        "to": to_date
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(BASE_URL_TINKOFF, headers=headers, json=params)
            response.raise_for_status()
            data = response.json()
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
                event_date = (
                    event.get("couponDate") or
                    event.get("COUPONDATE")
                )
                event_amount = (
                    event.get("payOneBond", {}).get("value") or
                    event.get("COUPONVALUE") or
                    event.get("couponValue")
                )
                event_type = (
                    event.get("couponType") or
                    event.get("type") or
                    "COUPON"
                )

                if event_date:
                    event_date = date.fromisoformat(event_date.split("T")[0])

                    if event_date == notify_date:
                        text = (
                            f"🔔 Напоминание: через 3 дня ({event_date}) у бумаги {bond.isin} — событие: {event_type.upper()}.\n"
                            f"Сумма купона: {event_amount} руб."
                        )
                        try:
                            await bot.send_message(chat_id=user.tg_id, text=text)
                            logging.info(f"✅ Уведомление отправлено: {user.full_name} — {bond.isin}")
                        except Exception as e:
                            logging.error(f"❌ Не удалось отправить уведомление: {e}")
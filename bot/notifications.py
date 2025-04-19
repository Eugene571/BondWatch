import httpx
import logging
from datetime import date, timedelta
from telegram import Bot
from bot.database import get_session, User
from database.figi_lookup import get_figi_by_ticker_and_classcode

# Константы для API
API_TOKEN = "t.yOBlCXQ3CL8QnMkpwSZZbLML7tbxqyucssGMrpv8i5nB4sgG36JlqRCfy456xOw3BjvWdfTCHIC7t5mcjuZL4Q"  # Токен для API T-Invest
BASE_URL = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetBondCoupons"


async def get_bond_coupons(figi: str, from_date: str, to_date: str):
    """Функция для получения информации о купонах облигации с API T-Invest."""
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    params = {
        "instrumentId": figi,  # идентификатор облигации
        "from": from_date,  # начало периода
        "to": to_date  # конец периода
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(BASE_URL, headers=headers, json=params)
            response.raise_for_status()  # Проверка на успешный запрос
            data = response.json()
            return data.get("events", [])  # Возвращаем список событий (купонов)
    except httpx.RequestError as e:
        logging.error(f"Ошибка при запросе к API T-Invest: {e}")
        return []


# Основная проверка уведомлений
async def check_and_notify(bot: Bot):
    logging.info("🔄 Проверка уведомлений запущена...")
    today = date.today()
    notify_date = today + timedelta(days=3)  # уведомления за 3 дня

    session = get_session()
    users = session.query(User).all()

    for user in users:
        for bond in user.tracked_bonds:
            # Получаем события (например, купоны) для облигации
            from_date = today.isoformat()  # текущая дата
            to_date = (today + timedelta(days=4)).isoformat()  # через 3 дня
            events = await get_bond_coupons(bond.figi, from_date, to_date)

            for event in events:
                event_date = event.get("couponDate")
                event_type = event.get("couponType")
                event_amount = event.get("payOneBond", {}).get("value", 0)

                # Преобразуем строку с датой в объект date
                event_date = date.fromisoformat(event_date.split("T")[0])

                if event_date == notify_date:
                    text = f"🔔 Напоминание: через 3 дня ({event_date}) у бумаги {bond.isin} — событие: {event_type.upper()}.\nСумма купона: {event_amount}."
                    try:
                        await bot.send_message(chat_id=user.tg_id, text=text)
                        logging.info(f"✅ Уведомление отправлено: {user.full_name} — {bond.isin}")
                    except Exception as e:
                        logging.error(f"❌ Не удалось отправить уведомление: {e}")

# database.bond_utils.py
from datetime import datetime, timedelta
from bot.notifications import get_bond_coupons_tinkoff
from database.moex_lookup import get_bond_coupons_from_moex


async def update_bond_coupon_info(bond, session, logger=print):
    today = datetime.utcnow()
    from_date = today
    to_date = today + timedelta(days=30)

    logger(f"🚀 Отправляем запрос на Tinkoff с параметрами: ")
    logger(f"from_date: {from_date}, to_date: {to_date}, instrumentId: {bond.figi}")

    events = []
    try:
        events = await get_bond_coupons_tinkoff(bond.figi, from_date, to_date)
        logger(f"✅ Получены данные с Tinkoff: {events}")
    except Exception as e:
        logger(f"⚠️ Ошибка при запросе купонов через Tinkoff: {e}")

    if not events:
        try:
            events = await get_bond_coupons_from_moex(bond.isin)
            logger(f"✅ Получены данные с MOEX: {events}")
        except Exception as e:
            logger(f"⚠️ Ошибка при запросе купонов через MOEX: {e}")

    if not events:
        logger("⚠️ Не удалось получить ни одного купонного события. Данные не обновлены.")
        return  # Не трогаем существующие значения

    updated = False
    for event in events:
        event_date_str = event.get("couponDate") or event.get("COUPONDATE")
        event_amount_units = event.get("payOneBond", {}).get("units")
        event_amount_nano = event.get("payOneBond", {}).get("nano")

        logger(f"Обрабатываем купонное событие: {event}")
        logger(f"Дата купона: {event_date_str}, Сумма (units): {event_amount_units}, Сумма (nano): {event_amount_nano}")

        if event_date_str and event_amount_units is not None and event_amount_nano is not None:
            try:
                event_date = datetime.fromisoformat(event_date_str.replace("Z", ""))
                logger(f"✅ Преобразованная дата купона: {event_date}")

                event_amount = int(event_amount_units) + int(event_amount_nano) / 1e9
                logger(f"✅ Полная сумма купона: {event_amount}")

                if event_date.date() > today.date():
                    bond.next_coupon_date = event_date.date()
                    bond.next_coupon_value = event_amount
                    session.commit()
                    logger(f"📌 Обновлены данные о купоне: дата = {event_date.date()}, сумма = {event_amount}")
                    updated = True
                    break
                else:
                    logger(f"⚠️ Купон в прошлом: дата = {event_date.date()}")
            except Exception as e:
                logger(f"⚠️ Ошибка при обработке купонного события: {e}")
        else:
            logger(f"⚠️ Данные купона некорректны: {event_date_str}, {event_amount_units}, {event_amount_nano}")

    if not updated:
        logger("⚠️ Все купонные события в прошлом или были некорректны. Данные не обновлены.")
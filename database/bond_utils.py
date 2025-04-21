# database.bond_utils.py
from datetime import datetime, timedelta
from bot.notifications import get_bond_coupons_tinkoff
from database.moex_lookup import get_bond_coupons_from_moex


async def update_bond_coupon_info(bond, session, logger=print):
    today = datetime.utcnow()  # Используем UTC для времени
    from_date = today
    to_date = today + timedelta(days=30)

    # Логируем параметры запроса
    logger(f"🚀 Отправляем запрос на Tinkoff с параметрами: ")
    logger(f"from_date: {from_date}, to_date: {to_date}, instrumentId: {bond.figi}")

    events = []
    # Пробуем Tinkoff
    try:
        # Передаем объекты datetime напрямую
        events = await get_bond_coupons_tinkoff(bond.figi, from_date, to_date)
    except Exception as e:
        logger(f"⚠️ Ошибка при запросе купонов через Tinkoff: {e}")

    # Фолбэк на MOEX
    if not events:
        try:
            events = await get_bond_coupons_from_moex(bond.isin)
        except Exception as e:
            logger(f"⚠️ Ошибка при запросе купонов через MOEX: {e}")

    for event in events:
        event_date_str = event.get("couponDate") or event.get("COUPONDATE")
        event_amount_units = event.get("payOneBond", {}).get("units")
        event_amount_nano = event.get("payOneBond", {}).get("nano")

        if event_date_str and event_amount_units is not None and event_amount_nano is not None:
            try:
                # Преобразуем строку даты из ответа в объект datetime
                event_date = datetime.fromisoformat(event_date_str.replace("Z", ""))

                # Рассчитываем полную сумму купона
                event_amount = int(event_amount_units) + int(event_amount_nano) / 1e9

                # Если дата купона в будущем, обновляем информацию
                if event_date.date() > today.date():  # Сравниваем только дату без времени
                    bond.next_coupon_date = event_date.date()
                    bond.next_coupon_value = event_amount
                    session.commit()
                    break
            except Exception as e:
                logger(f"⚠️ Ошибка при обработке купонного события: {e}")
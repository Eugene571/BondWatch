# database.bond_update
from datetime import datetime, timedelta
from database.moex_lookup import get_bond_coupons_from_moex
from bot.notifications import get_bond_coupons_tinkoff
import logging
from sqlalchemy.orm import Session
from bot.DB import TrackedBond


async def get_next_coupon(isin: str, figi: str | None, bond: TrackedBond, session: Session) -> None:
    today = datetime.today().date()
    one_year_later = today + timedelta(days=365)

    # Сначала пробуем через Tinkoff
    if figi:
        try:
            coupons = await get_bond_coupons_tinkoff(figi, from_date=str(today), to_date=str(one_year_later))
            upcoming = []
            for c in coupons:
                raw_date = c.get("date")
                if not raw_date:
                    continue
                try:
                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    if parsed_date >= today:
                        c["parsed_date"] = parsed_date
                        upcoming.append(c)
                except ValueError:
                    logging.warning(f"⚠️ Невалидная дата {raw_date} от TINKOFF для {figi}")
                    continue

            if upcoming:
                upcoming.sort(key=lambda x: x["parsed_date"])
                first = upcoming[0]
                logging.debug(f"💾 Первый купон для сохранения: {first}")
                bond.next_coupon_date = first["parsed_date"]
                bond.next_coupon_value = first["value"]
                session.commit()
                logging.debug(f"💾 Commit завершён, купон сохранён: {bond.next_coupon_date}, {bond.next_coupon_value}")
                logging.info(f"✅ Данные купона обновлены через TINKOFF для {bond.isin}")
                return
        except Exception as e:
            logging.warning(f"❌ Tinkoff купоны не получены для {figi}: {e}")

    # Если не получилось — пробуем MOEX
    try:
        coupons = await get_bond_coupons_from_moex(isin)
        logging.debug(f"🧾 Все купоны от MOEX для {isin}: {coupons}")

        upcoming = []
        for c in coupons:
            raw_date = c.get("couponDate")
            if not raw_date:
                continue
            try:
                parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                if parsed_date >= today:
                    c["parsed_date"] = parsed_date
                    upcoming.append(c)
            except ValueError:
                logging.warning(f"⚠️ Невалидная дата {raw_date} от MOEX для {isin}")
                continue

        logging.debug(f"🔍 Подходящие купоны от MOEX для {isin}: {upcoming}")

        if upcoming:
            upcoming.sort(key=lambda x: x["parsed_date"])
            first = upcoming[0]
            logging.debug(f"💾 Первый купон для сохранения: {first}")
            bond.next_coupon_date = first["parsed_date"]
            bond.next_coupon_value = first["couponValue"]
            session.commit()
            logging.debug(f"💾 Commit завершён, купон сохранён: {bond.next_coupon_date}, {bond.next_coupon_value}")
            logging.info(f"✅ Данные купона обновлены через MOEX для {bond.isin}")
            return
    except Exception as e:
        logging.warning(f"❌ MOEX купоны не получены для {isin}: {e}")

    logging.info(f"❌ Купоны не найдены для {isin}")
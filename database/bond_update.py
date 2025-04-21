
from datetime import datetime, timedelta
from database.moex_lookup import get_bond_coupons_from_moex
from bot.notifications import get_bond_coupons_tinkoff
import logging


async def get_next_coupon(isin: str, figi: str | None) -> dict | None:
    today = datetime.today().date()
    one_year_later = today + timedelta(days=365)

    # Сначала пробуем через Tinkoff
    if figi:
        try:
            coupons = await get_bond_coupons_tinkoff(figi, from_date=str(today), to_date=str(one_year_later))
            upcoming = [c for c in coupons if c.get("date") and c["date"] >= str(today)]
            if upcoming:
                upcoming.sort(key=lambda x: x["date"])
                first = upcoming[0]
                return {
                    "next_coupon_date": datetime.strptime(first["date"], "%Y-%m-%d").date(),
                    "next_coupon_value": first["value"]
                }
        except Exception as e:
            logging.warning(f"Tinkoff купоны не получены для {figi}: {e}")

    # Если нет — пробуем MOEX
    try:
        coupons = await get_bond_coupons_from_moex(isin)
        upcoming = [c for c in coupons if c.get("couponDate") and c["couponDate"] >= str(today)]
        if upcoming:
            upcoming.sort(key=lambda x: x["couponDate"])
            first = upcoming[0]
            return {
                "next_coupon_date": datetime.strptime(first["couponDate"], "%Y-%m-%d").date(),
                "next_coupon_value": first["couponValue"]
            }
    except Exception as e:
        logging.warning(f"MOEX купоны не получены для {isin}: {e}")

    return None

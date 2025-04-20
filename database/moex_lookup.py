# database.moex_lookup.py
import httpx
import logging


async def get_bond_coupons_from_moex(isin: str):
    """Получение купонов облигации с MOEX по ISIN через bondization.json."""
    url = f"https://iss.moex.com/iss/securities/{isin}/bondization.json"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        coupons_metadata = data.get("coupons", {}).get("columns", [])
        coupons_data = data.get("coupons", {}).get("data", [])

        # Безопасное определение индексов
        try:
            idx_date = coupons_metadata.index("coupondate")
            idx_value = coupons_metadata.index("value")
            idx_percent = coupons_metadata.index("percent")
        except ValueError as e:
            logging.error(f"❌ Не найдены нужные поля в bondization.json для {isin}: {e}")
            return []

        coupons = []
        for row in coupons_data:
            coupon_date = row[idx_date]
            if not coupon_date:
                continue

            coupons.append({
                "couponDate": str(coupon_date),
                "couponValue": row[idx_value] or 0,
                "couponPercent": row[idx_percent] or 0,
                "type": "COUPON"
            })

        return coupons

    except Exception as e:
        logging.error(f"❌ Ошибка при получении купонов с МОЕКС для {isin}: {e}")
        return []

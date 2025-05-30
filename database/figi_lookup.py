# database.figi_lookup.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("T_TOKEN")


async def get_figi_by_ticker_and_classcode(ticker: str, default_class_code: str = "TQCB") -> str:
    url = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/BondBy"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }

    class_codes_to_try = [default_class_code, "TQOB", "TQOD", "TQIR"]

    for class_code in class_codes_to_try:
        payload = {
            "idType": "INSTRUMENT_ID_TYPE_TICKER",
            "classCode": class_code,
            "id": ticker
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                instrument = data["instrument"]
                figi = instrument["figi"]
                name = instrument["name"]

                from database.update import update_tracked_bond_figi  # ⬅️ импорт внутрь
                await update_tracked_bond_figi(ticker, figi, class_code, name)

                return figi

            except (httpx.HTTPStatusError, KeyError):
                continue  # Пробуем следующий classCode

    # Если ни один classCode не сработал — записываем как не найденную
    from database.update import mark_bond_as_not_found
    await mark_bond_as_not_found(ticker)

    raise ValueError(f"❌ Не удалось найти FIGI для тикера {ticker}")

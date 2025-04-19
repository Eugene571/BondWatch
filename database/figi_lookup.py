import os
import httpx
from dotenv import load_dotenv
from bot.database import update_tracked_bond_figi  # Импортируем функцию для обновления данных в БД

load_dotenv()
TOKEN = os.getenv("T_TOKEN")


async def get_figi_by_ticker_and_classcode(ticker: str, class_code: str) -> str:
    url = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/BondBy"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }

    payload = {
        "idType": "INSTRUMENT_ID_TYPE_TICKER",
        "classCode": class_code,
        "id": ticker
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        figi = data["instrument"]["figi"]

        # Обновляем БД с полученным FIGI
        await update_tracked_bond_figi(ticker, figi, class_code)  # Обновление записи в БД

        return figi
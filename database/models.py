import httpx
import os
from dotenv import load_dotenv

load_dotenv()


API_TOKEN = os.getenv("T_TOKEN")
BASE_URL = "https://invest-public-api.tinkoff.ru/rest/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetBondCoupons"


async def test_get_bond_coupons():
    params = {
        "instrumentId": "BBG004730RP0",  # замените на figi облигации
        "from": "2025-04-19T00:00:00Z",  # начальная дата в формате UTC
        "to": "2025-04-22T00:00:00Z"  # конечная дата
    }

    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(BASE_URL, json=params, headers=headers)
        response.raise_for_status()  # Проверка успешности запроса
        data = response.json()
        print(data)  # Печать ответа для проверки


# Запустите тестовую функцию
import asyncio

asyncio.run(test_get_bond_coupons())

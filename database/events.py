from datetime import datetime
import asyncio
import httpx
import logging
import json
from typing import Dict, List

# Параметры запроса
URL_TEMPLATE = "https://iss.moex.com/iss/securities/{}/bondization.json"
EVENT_TYPES = ["amortizations", "coupons", "offers"]


async def fetch_bond_events(isin: str) -> Dict[str, List]:
    """
    Получает информацию о событиях облигации (амортизации, купоны, оферты) по ISIN с МосБиржи.
    :param isin: Уникальный номер облигации (ISIN)
    :return: Словарь с событиями облигации
    """
    url = URL_TEMPLATE.format(isin)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # Распаковка и формирование итогового результата
            result = {}
            for event_type in EVENT_TYPES:
                metadata = data[event_type].get("metadata", {})
                columns = data[event_type].get("columns", [])
                rows = data[event_type].get("data", [])

                # Формируем список событий
                events = []
                for row in rows:
                    event = dict(zip(columns, row))

                    # Конвертируем даты и очищаем лишние поля
                    for key in event.keys():
                        if "date" in key.lower() and isinstance(event[key], str):
                            event[key] = convert_date(event[key])

                    events.append(event)

                result[event_type] = events

            return result
    except Exception as e:
        logging.error(f"Ошибка при получении событий облигации {isin}: {e}")
        return {}


def convert_date(date_string: str) -> str:
    """
    Преобразование даты из формата YYYY-MM-DD в формат DD.MM.YYYY.
    """
    try:
        dt = datetime.strptime(date_string, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return date_string

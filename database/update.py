from datetime import datetime, timedelta
from database.figi_lookup import get_figi_by_ticker_and_classcode
from database.moex_name_lookup import get_bond_name_from_moex


async def update_tracked_bond_figi(isin: str, figi: str, class_code: str, name: str):
    from bot.database import get_session, TrackedBond
    session = get_session()
    try:
        bond = session.query(TrackedBond).filter_by(isin=isin).first()
        if bond:
            # Обновляем только FIGI и class_code, если FIGI не найдено, пытаемся получить имя с MOEX
            bond.figi = figi if figi else bond.figi
            bond.class_code = class_code
            if not bond.name and name:
                bond.name = name  # Обновляем имя только если оно найдено
            bond.last_updated = datetime.utcnow()
            session.commit()
    except Exception as e:
        print(f"Ошибка при обновлении облигации {isin}: {e}")
    finally:
        session.close()


async def update_bond_data():
    from bot.database import get_session, TrackedBond  # Переносим импорт внутрь функции
    session = get_session()  # Получаем сессию
    try:
        # Получаем все облигации, у которых данные устарели
        bonds_to_update = session.query(TrackedBond).filter(
            TrackedBond.last_updated < datetime.utcnow() - timedelta(days=1)
        ).all()

        for bond in bonds_to_update:
            try:
                # Получаем FIGI через Tinkoff
                figi = await get_figi_by_ticker_and_classcode(bond.isin, bond.class_code or "TQCB")

                # Если имя облигации не обновлено, пробуем получить его с MOEX
                if not bond.name:
                    name = await get_bond_name_from_moex(bond.isin)
                    if name:
                        bond.name = name

                # Обновляем FIGI и дату последнего обновления
                bond.figi = figi if figi else bond.figi
                bond.last_updated = datetime.utcnow()

                # Сохраняем изменения
                session.commit()

            except Exception as e:
                print(f"Ошибка при обновлении облигации {bond.isin}: {e}")
    finally:
        session.close()  # Закрываем сессию после завершения


async def mark_bond_as_not_found(isin: str):
    from bot.database import get_session, TrackedBond
    session = get_session()
    try:
        bond = session.query(TrackedBond).filter_by(isin=isin).first()
        if bond:
            bond.name = None  # Убираем значение "❌ Не найдена в API", если данные не найдены
            bond.last_updated = datetime.utcnow()
            session.commit()
    except Exception as e:
        print(f"Ошибка при отметке облигации {isin} как несуществующей: {e}")
    finally:
        session.close()
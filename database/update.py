# database/update.py
from datetime import datetime, timedelta
from database.figi_lookup import get_figi_by_ticker_and_classcode


async def update_tracked_bond_figi(isin: str, figi: str, class_code: str, name: str):
    """Обновить информацию о tracked_bond в базе данных"""
    from bot.database import get_session, TrackedBond  # Переносим импорт внутрь функции
    session = get_session()  # Получаем сессию
    try:
        bond = session.query(TrackedBond).filter_by(isin=isin).first()
        if bond:
            bond.figi = figi
            bond.class_code = class_code
            bond.name = name  # Сохраняем название
            bond.last_updated = datetime.utcnow()
            session.commit()
    except Exception as e:
        print(f"Ошибка при обновлении облигации {isin}: {e}")
    finally:
        session.close()  # Закрываем сессию после завершения


async def update_bond_data():
    from bot.database import get_session, TrackedBond  # Переносим импорт внутрь функции
    session = get_session()  # Получаем сессию
    try:
        # Получаем все облигации, у которых данные устарели
        bonds_to_update = session.query(TrackedBond).filter(
            TrackedBond.last_updated < datetime.utcnow() - timedelta(days=1)
        ).all()

        for bond in bonds_to_update:
            # Получаем новые данные для облигации
            try:
                figi = await get_figi_by_ticker_and_classcode(bond.isin, bond.class_code or "TQCB")

                # Обновляем FIGI и дату последнего обновления
                bond.figi = figi
                bond.last_updated = datetime.utcnow()

                # Сохраняем изменения
                session.commit()

            except Exception as e:
                print(f"Ошибка при обновлении облигации {bond.isin}: {e}")
    finally:
        session.close()  # Закрываем сессию после завершения

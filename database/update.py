# database.update.py
from datetime import datetime, timedelta
from database.figi_lookup import get_figi_by_ticker_and_classcode
from database.moex_name_lookup import get_bond_name_from_moex
from database.bond_update import get_next_coupon


async def update_tracked_bond_figi(isin: str, figi: str, class_code: str, name: str):
    from bot.database import get_session, TrackedBond
    session = get_session()
    try:
        bond = session.query(TrackedBond).filter_by(isin=isin).first()
        if bond:
            bond.figi = figi if figi else bond.figi
            bond.class_code = class_code
            if not bond.name and name:
                bond.name = name
            bond.last_updated = datetime.utcnow()

            # Обновим купон, если есть FIGI или хотя бы ISIN
            coupon_info = await get_next_coupon(bond.isin, bond.figi)
            if coupon_info:
                bond.next_coupon_date = coupon_info["next_coupon_date"]
                bond.next_coupon_value = coupon_info["next_coupon_value"]

            session.commit()
    except Exception as e:
        print(f"Ошибка при обновлении облигации {isin}: {e}")
    finally:
        session.close()


async def update_bond_data():
    from bot.database import get_session, TrackedBond
    session = get_session()
    try:
        bonds_to_update = session.query(TrackedBond).filter(
            TrackedBond.last_updated < datetime.utcnow() - timedelta(days=1)
        ).all()

        for bond in bonds_to_update:
            try:
                figi = await get_figi_by_ticker_and_classcode(bond.isin, bond.class_code or "TQCB")

                if not bond.name:
                    name = await get_bond_name_from_moex(bond.isin)
                    if name:
                        bond.name = name

                bond.figi = figi if figi else bond.figi
                bond.last_updated = datetime.utcnow()

                # Обновим купонную информацию
                coupon_info = await get_next_coupon(bond.isin, bond.figi)
                if coupon_info:
                    bond.next_coupon_date = coupon_info["next_coupon_date"]
                    bond.next_coupon_value = coupon_info["next_coupon_value"]

                session.commit()

            except Exception as e:
                print(f"Ошибка при обновлении облигации {bond.isin}: {e}")
    finally:
        session.close()


async def mark_bond_as_not_found(isin: str):
    from bot.database import get_session, TrackedBond
    session = get_session()
    try:
        bond = session.query(TrackedBond).filter_by(isin=isin).first()
        if bond:
            bond.name = None
            bond.last_updated = datetime.utcnow()
            session.commit()
    except Exception as e:
        print(f"Ошибка при отметке облигации {isin} как несуществующей: {e}")
    finally:
        session.close()

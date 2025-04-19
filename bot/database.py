from sqlalchemy import create_engine, Column, Integer, String, BigInteger, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Создаём движок SQLite
engine = create_engine("sqlite:///bot.db")
Session = sessionmaker(bind=engine)
Base = declarative_base()


def get_session():
    return Session()


def init_db():
    Base.metadata.create_all(engine)


async def update_tracked_bond_figi(isin: str, figi: str, class_code: str):
    """Обновить информацию о tracked_bond в базе данных"""
    session = get_session()
    bond = session.query(TrackedBond).filter_by(isin=isin).first()
    if bond:
        bond.figi = figi
        bond.class_code = class_code
        session.commit()


# Модель пользователя
class User(Base):
    __tablename__ = "users"

    tg_id = Column(BigInteger, primary_key=True)
    full_name = Column(String)

    tracked_bonds = relationship(
        "TrackedBond", back_populates="user", cascade="all, delete-orphan"
    )


# Модель отслеживаемой облигации
class TrackedBond(Base):
    __tablename__ = "tracked_bonds"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.tg_id"))
    isin = Column(String(12), nullable=False)
    figi = Column(String, nullable=True)  # Добавили поле для FIGI
    class_code = Column(String, nullable=True)  # Добавили поле для class_code
    added_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tracked_bonds")

# bot.DB.py

from sqlalchemy import create_engine, Column, Integer, String, BigInteger, ForeignKey, DateTime, Date, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta

# Создаём движок SQLite
engine = create_engine("sqlite:///bot.db")
Session = sessionmaker(bind=engine)
Base = declarative_base()


def get_session():
    return Session()


# Функция для инициализации базы данных
def init_db():
    # Создаём все таблицы, если они ещё не существуют
    Base.metadata.create_all(engine)


# Модель пользователя
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)  # primary_key для id
    tg_id = Column(BigInteger, unique=True)  # Уникальный tg_id
    full_name = Column(String)

    tracked_bonds = relationship(
        "TrackedBond", back_populates="user", cascade="all, delete-orphan"
    )


# Модель отслеживаемой облигации
class TrackedBond(Base):
    __tablename__ = "tracked_bonds"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.tg_id"))  # Ссылаемся на tg_id
    isin = Column(String, nullable=False)
    name = Column(String)
    figi = Column(String, nullable=True)
    class_code = Column(String, nullable=True)
    ticker = Column(String, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    next_coupon_date = Column(Date, nullable=True)
    next_coupon_value = Column(Float, nullable=True)

    user = relationship("User", back_populates="tracked_bonds")

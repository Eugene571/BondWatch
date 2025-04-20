# bot/database.py

from sqlalchemy import create_engine, Column, Integer, String, BigInteger, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta

from database.update import update_tracked_bond_figi  # Импортируем функцию для обновления данных в БД

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
    name = Column(String, nullable=True)
    isin = Column(String(12), nullable=False)
    figi = Column(String, nullable=True)  # Поле для FIGI
    class_code = Column(String, nullable=True)  # Поле для class_code
    added_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)  # Поле для даты последнего обновления

    user = relationship("User", back_populates="tracked_bonds")

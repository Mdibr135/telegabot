from sqlalchemy import BigInteger, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


# Таблица пользователей (и водители, и пассажиры)
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Здесь будет храниться Telegram ID
    username: Mapped[str | None] = mapped_column(String(64))  # Юзернейм в Телеграм (@username)
    first_name: Mapped[str] = mapped_column(String(64))  # Имя человека
    phone_number: Mapped[str | None] = mapped_column(String(20))  # Телефон для связи

    # Связь: один пользователь может создать много поездок
    trips = relationship("Trip", back_populates="driver")


# Таблица самих поездок
class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # Номер поездки
    driver_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))  # Кто водитель (его Telegram ID)
    from_city: Mapped[str] = mapped_column(String(100))  # Откуда (например, Душанбе)
    to_city: Mapped[str] = mapped_column(String(100))  # Куда (например, Худжанд)
    departure_time: Mapped[datetime] = mapped_column(DateTime)  # Дата и время выезда
    total_seats: Mapped[int] = mapped_column(Integer, default=4)  # Сколько всего мест
    available_seats: Mapped[int] = mapped_column(Integer, default=4)  # Сколько мест осталось
    price_per_seat: Mapped[int] = mapped_column(Integer)  # Цена в сомони
    comment: Mapped[str | None] = mapped_column(Text)  # Комментарий к поездке
    status: Mapped[str] = mapped_column(String(20), default="active")  # Статус (active/completed)

    # Связь обратно к водителю, чтобы знать, кто едет
    driver = relationship("User", back_populates="trips")
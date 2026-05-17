import os
from dotenv import load_dotenv
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import BigInteger, Integer, String, DateTime, Text, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config import settings
from app.database import init_db, get_db
from app.models import Base, User, Trip

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot_client = Bot(token=TELEGRAM_TOKEN)



app = FastAPI(title="Попутчик Таджикистан API")


# Разрешаем доступ к API с любых устройств (нужно для работы внутри Telegram)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Автоматически создаем базу данных и таблицы при старте сервера
@app.on_event("startup")
async def on_startup():
    await init_db()


# --- Вспомогательные схемы для проверки входящих данных ---
# --- НОВАЯ МОДЕЛЬ ТАБЛИЦЫ БРОНИРОВАНИЙ В БД ---
class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(Integer, ForeignKey("trips.id"), nullable=False)
    passenger_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, confirmed, rejected

    # Отношения (чтобы легко подтягивать связанные данные)
    trip = relationship("Trip")
    passenger = relationship("User")

class UserSchema(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: str
    phone_number: Optional[str] = None


class TripCreateSchema(BaseModel):
    from_city: str
    to_city: str
    departure_time: datetime
    total_seats: int
    price_per_seat: int
    comment: Optional[str] = None

class BookingCreateSchema(BaseModel):
    trip_id: int
    passenger_id: int


# --- ЭНДПОИНТЫ (КОМАНДЫ ДЛЯ ДИСПЕТЧЕРА) ---

# 1. Регистрация или обновление профиля пользователя
# Тестовый эндпоинт проверки здоровья сервера (Health Check)
@app.api_route("/", methods=["GET", "HEAD", "POST"])
async def root():
    return {"status": "working", "message": "API сервиса Попутчик готово к работе."}

@app.post("/users/")
async def register_or_update_user(user_data: UserSchema, db: AsyncSession = Depends(get_db)):
    # Проверяем, есть ли уже этот человек в нашей базе
    result = await db.execute(select(User).where(User.id == user_data.id))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Если есть, просто обновляем его имя и юзернейм (вдруг он их поменял в Telegram)
        existing_user.username = user_data.username
        existing_user.first_name = user_data.first_name
        if user_data.phone_number:
            existing_user.phone_number = user_data.phone_number
        await db.commit()
        return {"status": "updated", "message": "Профиль пользователя обновлен"}

    # Если человека нет, записываем его как нового клиента
    new_user = User(
        id=user_data.id,
        username=user_data.username,
        first_name=user_data.first_name,
        phone_number=user_data.phone_number
    )
    db.add(new_user)
    await db.commit()
    return {"status": "created", "message": "Пользователь успешно зарегистрирован"}


# 2. Создание поездки водителем
@app.post("/trips/")
async def create_trip(driver_id: int, trip_data: TripCreateSchema, db: AsyncSession = Depends(get_db)):
    # Проверяем, зарегистрирован ли вообще этот водитель у нас
    user_result = await db.execute(select(User).where(User.id == driver_id))
    driver = user_result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Сначала зарегистрируйте пользователя!")

    # Создаем новую запись о поездке
    new_trip = Trip(
        driver_id=driver_id,
        from_city=trip_data.from_city,
        to_city=trip_data.to_city,
        departure_time=trip_data.departure_time,
        total_seats=trip_data.total_seats,
        available_seats=trip_data.total_seats,  # В начале свободны все места
        price_per_seat=trip_data.price_per_seat,
        comment=trip_data.comment
    )
    db.add(new_trip)
    await db.commit()
    return {"status": "success", "message": "Поездка успешно добавлена!"}


# 3. Поиск поездок для пассажира
@app.get("/trips/search/")
async def search_trips(from_city: str, to_city: str, travel_date: date, db: AsyncSession = Depends(get_db)):
    # Находим начало и конец выбранного дня, чтобы искать поездки на эти сутки
    start_of_day = datetime.combine(travel_date, datetime.min.time())
    end_of_day = datetime.combine(travel_date, datetime.max.time())

    # Запрос к базе: найти активные поездки по маршруту, где есть свободные места
    query = select(Trip).where(
        Trip.from_city == from_city,
        Trip.to_city == to_city,
        Trip.status == "active",
        Trip.available_seats > 0,
        Trip.departure_time >= start_of_day,
        Trip.departure_time <= end_of_day
    )

    result = await db.execute(query)
    trips = result.scalars().all()
    return trips

# 4. Создание брони (Пассажир нажимает кнопку «Бронь» в интерфейсе)
@app.post("/bookings/")
async def create_booking(booking_data: BookingCreateSchema, db: AsyncSession = Depends(get_db)):
    # Вытягиваем информацию о поездке
    trip_result = await db.execute(select(Trip).where(Trip.id == booking_data.trip_id))
    trip = trip_result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if trip.available_seats <= 0:
        raise HTTPException(status_code=400, detail="Свободных мест больше нет")

    # Вытягиваем информацию о пассажире
    passenger_result = await db.execute(select(User).where(User.id == booking_data.passenger_id))
    passenger = passenger_result.scalar_one_or_none()
    if not passenger:
        raise HTTPException(status_code=404, detail="Пассажир не зарегистрирован в системе")

    # Создаем саму запись бронирования со статусом ожидания
    new_booking = Booking(trip_id=booking_data.trip_id, passenger_id=booking_data.passenger_id)
    db.add(new_booking)
    await db.commit()
    await db.refresh(new_booking)

    # ОТПРАВЛЯЕМ МГНОВЕННОЕ УВЕДОМЛЕНИЕ ВОДИТЕЛЮ В ТЕЛЕГРАМ
    try:
        # Прикрепляем инлайн-кнопки действия, вшивая в них ID нашей брони
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Согласиться", callback_data=f"confirm_{new_booking.id}"),
                InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_{new_booking.id}")
            ]
        ])

        notification_text = (
            f"🔔 <b>Новая заявка на поездку!</b>\n\n"
            f"👤 Пассажир: {passenger.first_name} (@{passenger.username or 'нет'})\n"
            f"🚗 Маршрут: {trip.from_city} → {trip.to_city}\n"
            f"💰 Цена: {trip.price_per_seat} сомони\n"
            f"🚘 Машина/Комментарий: {trip.comment or 'нет'}\n\n"
            f"Вы согласны взять этого попутчика?")

        await bot_client.send_message(
            chat_id=trip.driver_id, 
            text=notification_text, 
            parse_mode="HTML", # Переключили на HTML
            reply_markup=keyboard)
        
    except Exception as e:
        print(f"Ошибка отправки уведомления ботом: {e}")

    return {"status": "pending", "booking_id": new_booking.id, "message": "Заявка отправлена водителю"}


# 5. Подтверждение брони (Срабатывает, когда Водитель жмет «Согласиться» в боте)
@app.patch("/bookings/{booking_id}/confirm")
async def confirm_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    booking_result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = booking_result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")
    
    if booking.status != "pending":
        return {"status": "already_processed", "message": f"Эта заявка уже обработана. Текущий статус: {booking.status}"}

    # Ищем поездку, чтобы забрать 1 свободное место
    trip_result = await db.execute(select(Trip).where(Trip.id == booking.trip_id))
    trip = trip_result.scalar_one_or_none()
    
    if trip.available_seats <= 0:
        booking.status = "rejected"
        await db.commit()
        try:
            await bot_client.send_message(chat_id=booking.passenger_id, text=f"😞 К сожалению, в машине {trip.from_city} → {trip.to_city} только что закончились свободные места.")
        except: pass
        raise HTTPException(status_code=400, detail="Свободных мест больше нет")

    # Меняем статус брони и уменьшаем остаток мест в машине
    booking.status = "confirmed"
    trip.available_seats -= 1
    await db.commit()

    # Отправляем радостное сообщение Пассажиру в ЛС
    try:
        driver_result = await db.execute(select(User).where(User.id == trip.driver_id))
        driver = driver_result.scalar_one_or_none()
        
        success_text = (
            f"🎉 *Отличные новости! Водитель одобрил вашу бронь!*\n\n"
            f"🚗 Поездка: {trip.from_city} → {trip.to_city}\n"
            f"👤 Водитель: {driver.first_name} (@{driver.username or 'нет'})\n"
            f"💵 Стоимость: {trip.price_per_seat} TJS\n"
            f"📉 Свободных мест в машине осталось: {trip.available_seats}"
        )
        await bot_client.send_message(chat_id=booking.passenger_id, text=success_text, parse_mode="HTML")
    except Exception as e:
        print(f"Не удалось отправить уведомление пассажиру: {e}")

    return {"status": "confirmed", "available_seats": trip.available_seats}


# 6. Отклонение брони (Срабатывает, когда Водитель жмет «Отказать» в боте)
@app.patch("/bookings/{booking_id}/reject")
async def reject_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    booking_result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = booking_result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")

    if booking.status != "pending":
        return {"status": "already_processed"}

    booking.status = "rejected"
    await db.commit()

    # Пишем грустное сообщение Пассажиру
    try:
        trip_result = await db.execute(select(Trip).where(Trip.id == booking.trip_id))
        trip = trip_result.scalar_one_or_none()
        
        await bot_client.send_message(
            chat_id=booking.passenger_id, 
            text=f"❌ К сожалению, водитель отклонил вашу заявку на поездку {trip.from_city} → {trip.to_city}."
        )
    except Exception as e:
        print(f"Не удалось отправить отказ пассажиру: {e}")

    return {"status": "rejected"}

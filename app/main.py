from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional

from app.database import init_db, get_db
from app.models import User, Trip

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


# --- ЭНДПОИНТЫ (КОМАНДЫ ДЛЯ ДИСПЕТЧЕРА) ---

# 1. Регистрация или обновление профиля пользователя
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
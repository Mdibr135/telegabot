import os
from dotenv import load_dotenv
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Загружаем переменные из .env файла
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Адрес нашего запущенного бэкенда (FastAPI) на Render
BACKEND_URL = "https://telegabot-77m2.onrender.com"

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


# Функция автоматической регистрации пользователя на бэкенде
async def register_user_in_backend(user_id: int, username: str, first_name: str):
    payload = {
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "phone_number": None  # Телефон заполнится позже внутри Mini App
    }

    async with aiohttp.ClientSession() as session:
        try:
            # ИСПРАВЛЕНО: добавили /users/, чтобы данные попадали в таблицу пользователей
            async with session.post(f"{BACKEND_URL}/users/", json=payload) as response:
                if response.status in [200, 201]:
                    logging.info(f"Пользователь {user_id} успешно синхронизирован с бэкендом.")
                else:
                    logging.error(f"Ошибка бэкенда при регистрации: статус {response.status}")
        except Exception as e:
            logging.error(f"Не удалось связаться с бэкендом для регистрации: {e}")


# Обработка команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без_юзернейма"
    first_name = message.from_user.first_name

    # 1. Автоматически регистрируем пользователя в нашей базе данных
    await register_user_in_backend(user_id, username, first_name)

    # 2. Создаем кнопку для запуска Mini App
    kb = InlineKeyboardBuilder()

    # Ссылка на фронтенд Mini App
    demo_web_app_url = "https://mdibr135.github.io/telegabot"

    kb.row(
        types.InlineKeyboardButton(
            text="🚗 Найти попутчика / Предложить поездку",
            web_app=types.WebAppInfo(url=demo_web_app_url)  # ИСПРАВЛЕНО: используем переменную
        )
    )

    # Приветственный текст
    welcome_text = (
        f"Салом, {first_name}! 👋\n\n"
        f"Добро пожаловать в сервис **Попутчик Таджикистан**!\n"
        f"Помогаем быстро и комфортно находить попутные машины по направлениям "
        f"Душанбе, Худжанд, Бохтар, Куляб и другим городам.\n\n"
        f"Нажми на кнопку ниже, чтобы открыть приложение 👇"
    )

    await message.answer(welcome_text, reply_markup=kb.as_markup(), parse_mode="Markdown")


# --- ОБРАБОТКА НАЖАТИЯ КНОПОК ВОДИТЕЛЕМ ---

# 1. Водитель нажал «Согласиться»
@dp.callback_query(F.data.startswith("confirm_"))
async def handle_confirm_booking(callback: types.CallbackQuery):
    booking_id = callback.data.split("_")[1]
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(f"{BACKEND_URL}/bookings/{booking_id}/confirm") as response:
                if response.status == 200:
                    await callback.message.edit_text(
                        text=callback.message.text + "\n\n🟢 *Вы одобрили эту заявку! Пассажир уведомлен.*",
                        parse_mode="Markdown",
                        reply_markup=None # Удаляем кнопки, чтобы нельзя было нажать дважды
                    )
                elif response.status == 400:
                    await callback.answer("Ошибка: Свободных мест больше нет!", show_alert=True)
                    await callback.message.edit_text(callback.message.text + "\n\n❌ *Места закончились, заявка отклонена.*", reply_markup=None)
                else:
                    await callback.answer("Произошла ошибка на сервере.", show_alert=True)
        except Exception as e:
            logging.error(f"Ошибка при подтверждении брони: {e}")
            await callback.answer("Не удалось связаться с сервером.", show_alert=True)


# 2. Водитель нажал «Отказать»
@dp.callback_query(F.data.startswith("reject_"))
async def handle_reject_booking(callback: types.CallbackQuery):
    booking_id = callback.data.split("_")[1]
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(f"{BACKEND_URL}/bookings/{booking_id}/reject") as response:
                if response.status == 200:
                    await callback.message.edit_text(
                        text=callback.message.text + "\n\n🔴 *Вы отклонили эту заявку. Пассажиру отправлен отказ.*",
                        parse_mode="Markdown",
                        reply_markup=None
                    )
                else:
                    await callback.answer("Произошла ошибка на сервере.", show_alert=True)
        except Exception as e:
            logging.error(f"Ошибка при отклонении брони: {e}")
            await callback.answer("Не удалось связаться с сервером.", show_alert=True)


# Главная функция запуска бота
async def main():
    logging.info("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

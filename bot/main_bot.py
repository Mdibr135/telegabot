import os
from dotenv import load_dotenv
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Токен твоего бота
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Адрес нашего запущенного бэкенда (FastAPI)
# Пока тестируем локально, адрес такой. Когда выложим в интернет, поменяем на домен.
BACKEND_URL = "https://telegabot-77m2.onrender.com/"

# Настраиваем логирование, чтобы видеть в терминале, если что-то пойдет не так
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


# Функция, которая незаметно для пользователя регистрирует его на бэкенде
async def register_user_in_backend(user_id: int, username: str, first_name: str):
    payload = {
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "phone_number": None  # Телефон пользователь заполнит позже внутри Mini App
    }

    # Асинхронно отправляем JSON-записку нашему FastAPI диспетчеру
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(BACKEND_URL, json=payload) as response:
                if response.status == 200:
                    logging.info(f"Пользователь {user_id} успешно синхронизирован с бэкендом.")
                else:
                    logging.error(f"Ошибка бэкенда: статус {response.status}")
        except Exception as e:
            logging.error(f"Не удалось связаться с бэкендом: {e}")


# Обработка команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "без_юзернейма"
    first_name = message.from_user.first_name

    # 1. Автоматически регистрируем пользователя в нашей базе данных
    await register_user_in_backend(user_id, username, first_name)

    # 2. Создаем кнопку со специальным типом WebApp (это и есть запуск Mini App!)
    kb = InlineKeyboardBuilder()

    # Пока у нас нет готового фронтенда, мы временно подключим официальный демо-сайт
    # чтобы проверить, как открывается встроенный браузер в Telegram
    demo_web_app_url = "https://mdibr135.github.io/telegabot/"
    # Примечание: Для реального теста мы можем использовать любой рабочий сайт, например "https://google.com"

    kb.row(
        types.InlineKeyboardButton(
            text="🚗 Найти попутчика / Предложить поездку",
            web_app=types.WebAppInfo(url="https://mdibr135.github.io/telegabot/")  # Временно открываем Google для проверки механизма
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

# 1. Водитель нажал «Согласиться»
# Фильтр F.data.startswith("confirm_") ловит колбэки вроде "confirm_12"
@dp.callback_query(F.data.startswith("confirm_"))
async def handle_confirm_booking(callback: types.CallbackQuery):
    # Вытаскиваем ID бронирования из даты кнопки (все, что после нижнего подчеркивания)
    booking_id = callback.data.split("_")[1]
    
    # Отправляем запрос на бэкенд, чтобы подтвердить бронь и вычесть место
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(f"{BACKEND_URL}/bookings/{booking_id}/confirm") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Если бэкенд ответил, что всё ок, меняем текст у водителя
                    await callback.message.edit_text(
                        text=callback.message.text + "\n\n🟢 *Вы одобрили эту заявку! Пассажир уведомлен.*",
                        parse_mode="Markdown",
                        reply_markup=None # Удаляем инлайн-кнопки, чтобы нельзя было нажать дважды
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

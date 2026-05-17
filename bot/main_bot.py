import os
from dotenv import load_dotenv
import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Токен твоего бота
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Адрес нашего запущенного бэкенда (FastAPI)
# Пока тестируем локально, адрес такой. Когда выложим в интернет, поменяем на домен.
BACKEND_URL = "https://telegabot-77m2.onrender.com/users/"

# Настраиваем логирование, чтобы видеть в терминале, если что-то пойдет не так
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
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
    demo_web_app_url = "https://telegram.org/js/telegram-web-app.js"
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


# Главная функция запуска бота
async def main():
    logging.info("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

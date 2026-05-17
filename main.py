import multiprocessing
import os
import uvicorn
from app.main_server import app

def run_backend():
    # Укажите импорт вашего приложения. Например, если в api.py у вас app = FastAPI()
    # uvicorn.run("api:app", host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
    print("Запуск бэкенда...")
    os.system("uvicorn app.main_server:app --reload)

def run_bot():
    print("Запуск Telegram-бота...")
    os.system("python -m bot.main_bot")

if __name__ == "__main__":
    # Запускаем бота в отдельном процессе
    bot_process = multiprocessing.Process(target=run_bot)
    bot_process.start()

    # Запускаем бэкенд в главном процессе (Render требует, чтобы веб-сервер оставался активным)
    run_backend()

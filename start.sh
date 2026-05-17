# Запускаем FastAPI на порту, который выделит Render ($PORT)
uvicorn app.main_server:app --host 0.0.0.0 --port $PORT &

# Запускаем Телеграм-бота
python bot/main_bot.py

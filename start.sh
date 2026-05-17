# Запускаем FastAPI на порту, который выделит Render ($PORT)
uvicorn app.main_server:app --host 0.0.0.0 --port $PORT &

# Запускаем Телеграм-бота
python -m bot/main_bot

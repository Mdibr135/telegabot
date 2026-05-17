# Запускаем FastAPI на порту, который выделит Render ($PORT)
echo "Запуск FastAPI бэкенда..."
uvicorn app.main_server:app --host 0.0.0.0 --port $PORT &
sleep 5
echo "Запуск Телеграм-бота..."
python bot/main_bot.py

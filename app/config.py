from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Указываем компьютеру использовать базу данных SQLite в файле poputchik.db
    DATABASE_URL: str = "sqlite+aiosqlite:///./poputchik.db"

settings = Settings()
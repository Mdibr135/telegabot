from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models import Base

# Создаем движок базы данных
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Делаем фабрику сессий (чтобы открывать/закрывать журнал)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Эта функция создаст файл poputchik.db и таблицы в нем, если их еще нет
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Помощник для выдачи доступа к базе данных нашим эндпоинтам
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
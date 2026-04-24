import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from app.core.clients import AIService, AsyncVKApiClient
from app.core.config import settings
from app.core.logger import setup_logging
from app.database.db_helper import DBHelper
from app.database.models import Base
from app.modules.analyzer.router import router as analyzer_router
from app.modules.chat_bot.router import router as chat_bot_router
from app.modules.generator.router import router as generator_router

if not os.path.exists("media"):
    os.makedirs("media")

if not os.path.exists("logs"):
    os.makedirs("logs")

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.vk_client = AsyncVKApiClient(
        api_keys={
            "groups.getById": settings.vk_service_token.get_secret_value(),
            "groups.getOnlineStatus": settings.vk_group_token.get_secret_value(),
            "groups.getMembers": settings.vk_group_token.get_secret_value(),
            "wall.get": settings.vk_service_token.get_secret_value(),
            "messages.send": settings.vk_group_token.get_secret_value(),
        },
    )
    app.state.ai_client = AIService(
        api_key=settings.ai_service_api_key.get_secret_value(),
    )
    app.state.redis_client = Redis(host="localhost", port=6379, db=0)

    app.state.db = DBHelper(
        f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/myapp",
        False,
        False,
    )
    async with app.state.db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await app.state.vk_client.aclose()
    await app.state.ai_client.aclose()
    await app.state.redis_client.aclose()
    await app.state.db.engine.dispose()


app = FastAPI(
    title="VK Mini App Backend",
    description="Backend для анализа сообществ и генерации контента",
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tunnel.wonderrfau1t.site", "https://vk.com", "https://vk.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory="media"), name="media")
app.include_router(analyzer_router, prefix="/api/v1/analyzer", tags=["Анализ сообществ"])
app.include_router(generator_router, prefix="/api/v1/generator", tags=["Генерация контента"])
app.include_router(chat_bot_router, prefix="/api/v1/chat", tags=["Чат-бот группы"])

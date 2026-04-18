from fastapi import FastAPI

from app.modules.analyzer.router import router as analyzer_router
from app.modules.chat_bot.router import router as chat_bot_router
from app.modules.generator.router import router as generator_router

app = FastAPI(
    title="VK Mini App Backend",
    description="Backend для анализа сообществ и генерации контента",
    version="1.0",
)

app.include_router(analyzer_router, prefix="/api/v1/analyzer", tags=["Анализ сообществ"])
app.include_router(generator_router, prefix="/api/v1/generator", tags=["Генерация контента"])
app.include_router(chat_bot_router, prefix="/api/v1/chat", tags=["Чат-бот группы"])

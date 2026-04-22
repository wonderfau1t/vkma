import logging
import sys
from loguru import logger  # Рекомендую использовать loguru для FastAPI

def setup_logging():
    # Удаляем стандартные обработчики
    logging.getLogger().handlers = []
    
    # Настраиваем формат для стандартного логирования (чтобы Uvicorn писал красиво)
    intercept_handler = InterceptHandler()
    logging.getLogger("uvicorn.access").handlers = [intercept_handler]
    logging.getLogger("uvicorn.error").handlers = [intercept_handler]

    # Конфигурация Loguru
    logger.configure(
        handlers=[
            {"sink": sys.stdout, "level": "DEBUG", "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"},
            {"sink": "logs/api.log", "serialize": False, "rotation": "10 MB", "retention": "7 days"}
        ]
    )

class InterceptHandler(logging.Handler):
    """
    Перехватчик стандартных логов python и перенаправление их в Loguru
    """
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
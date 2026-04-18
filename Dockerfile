FROM python:3.12-slim

# Установка uv
RUN pip install uv

# Рабочая директория
WORKDIR /app

# Копируем только зависимости (для кеша!)
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости
RUN uv sync --frozen --no-dev

# Копируем остальной код
COPY . .

EXPOSE 8000

# Команда запуска
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
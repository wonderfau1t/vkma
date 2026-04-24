import base64
import io
import os

from loguru import logger
from openai import APIStatusError, AsyncOpenAI, BadRequestError, OpenAIError, RateLimitError


class AIService:
    def __init__(self, api_key: str, base_url: str = "https://api.aitunnel.ru/v1/"):
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    async def aclose(self):
        await self._client.close()

    async def generate_image(
        self,
        prompt: str,
        image_name: str,
        model: str = "gemini-2.5-flash-image",
        reference_image: bytes | None = None,
        aspect_ratio: str | None = None,
    ):
        extra = {
            "image_config": {
                "aspect_ratio": aspect_ratio,
            }
        } if aspect_ratio else {}
        logger.info(
            f"Генерация изображения [{image_name}]: "
            f"референс={'да' if reference_image else 'нет'}, "
            f"aspect_ratio={aspect_ratio or 'не указан'}"
        )
        try:
            if reference_image:
                image_file = io.BytesIO(reference_image)
                image_file.name = "reference.png"
                response = await self._client.images.edit(
                    model=model, image=image_file, prompt=prompt, extra_body=extra
                )
            else:
                response = await self._client.images.generate(
                    model=model, prompt=prompt, extra_body=extra
                )

            if not response.data or not response.data[0]:
                raise ValueError("API вернул пустой список данных")

            image_data = response.data[0].url
            if not image_data:
                raise ValueError("В объекте ответа отсутствуют и данные изображения, и URL")

            path = self._save_image(image_data, image_name)
            if not path:
                raise RuntimeError(f"Не удалось сохранить изображение по пути: {image_name}")

            return path, self._extract_cost_rub(response)
        except BadRequestError as e:
            # Ошибка промпта (например, цензура или неверные параметры)
            logger.error(f"Некорректный запрос (цензура?): {e}")
            raise
        except RateLimitError as e:
            # Закончились деньги или лимиты в минуту
            logger.warning(f"Превышены лимиты запросов: {e}")
            raise
        except APIStatusError as e:
            # Ошибка на стороне серверов OpenAI (500, 502 и т.д.)
            logger.error(f"Сервер OpenAI ответил ошибкой {e.status_code}: {e.message}")
            raise
        except OpenAIError as e:
            # Базовый класс для всех ошибок библиотеки OpenAI
            logger.error(f"Общая ошибка OpenAI: {e}")
            raise
        except Exception as e:
            # Непредвиденные ошибки (проблемы с сетью, ОС, сохранением файла)
            logger.exception(f"Непредвиденная системная ошибка: {e}")
            raise

    async def generate_post(self, prompt: str, task_id: str, model: str = "gpt-4.1-nano"):
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты — эксперт по SMM и копирайтингу с 10-летним опытом. Твоя задача — создавать виральные и полезные посты для соцсетей (Instagram, Telegram, VK). "
                            "Придерживайся следующих правил:"
                            "1. Заголовок: Всегда начинай с цепляющего заголовка, который бьет в боль или интерес аудитории."
                            '2. Тон: Дружелюбный, экспертный, но доступный. Избегай официоза и "воды".'
                            "3. Структура: Используй абзацы для читаемости и списки (буллиты), если это уместно."
                            "4. Призыв к действию (CTA): Каждый пост должен заканчиваться вопросом к аудитории или четким призывом (подписаться, перейти по ссылке, сохранить)."
                            "5. Визуал: Описывай в конце поста идею для подходящей фотографии или картинки."
                            "6. Эмодзи: Используй их умеренно для акцентов, не перегружай текст."
                            "Пиши на языке пользователя, адаптируй стиль под контекст темы."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
            )
            if not response.choices:
                logger.error(f"[{task_id}] API вернул пустой список вариантов (choices)")
                raise ValueError("OpenAI вернул пустой ответ")

            message = response.choices[0].message

            # Проверка на пустой контент (иногда API может вернуть пустую строку при ошибке фильтрации контента)
            if not message.content or message.content.strip() == "":
                logger.warning(f"[{task_id}] Получено пустое сообщение от модели")
                raise ValueError("Модель сгенерировала пустой текст")

            return message.content, self._extract_cost_rub(response)

        except BadRequestError as e:
            # Неверные параметры или срабатывание фильтров безопасности контента
            logger.error(f"[{task_id}] Ошибка запроса (возможно, запрещенная тема): {e}")
            raise
        except RateLimitError as e:
            # Превышение лимитов (закончились токены или слишком много запросов в секунду)
            logger.warning(f"[{task_id}] Лимит запросов исчерпан: {e}")
            raise
        except APIStatusError as e:
            # Проблемы на стороне серверов OpenAI
            logger.error(f"[{task_id}] Ошибка сервиса OpenAI (Status: {e.status_code})")
            raise
        except OpenAIError as e:
            # Общая ошибка библиотеки
            logger.error(f"[{task_id}] Ошибка OpenAI SDK: {e}")
            raise
        except Exception as e:
            # Любые другие ошибки (сеть, тайм-ауты, ошибки кода)
            logger.exception(f"[{task_id}] Критическая ошибка при генерации поста: {e}")
            raise

    @staticmethod
    def _extract_cost_rub(response) -> float | None:
        usage = getattr(response, "usage", None)
        return getattr(usage, "cost_rub", None)

    def _save_image(self, image_b64: str, image_name: str):
        if "," in image_b64:
            image_b64 = image_b64.split(",")[1]
        try:
            # 2. Проверяем/создаем папку для медиа
            directory = "media"
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Создана директория: {directory}")

            # 3. Декодируем base64 в бинарные данные
            try:
                img_data = base64.b64decode(image_b64, validate=True)
            except Exception as e:
                logger.error(f"Ошибка валидации base64: {e}")
                return None

            # 4. Формируем путь и сохраняем
            file_name = f"{image_name}.png"
            file_path = os.path.join(directory, file_name)

            # Используем контекстный менеджер для безопасной записи
            with open(file_path, "wb") as img_file:
                img_file.write(img_data)

            logger.info(f"Изображение успешно сохранено: {file_path}")
            return file_name  # Или file_path, если вам нужен полный путь

        except PermissionError:
            logger.error(f"Ошибка доступа: нет прав на запись в директорию {directory}")
        except OSError as e:
            logger.error(f"Системная ошибка ввода-вывода при сохранении {image_name}: {e}")
        except Exception as e:
            logger.exception(f"Непредвиденная ошибка в _save_image: {e}")

        return None

import base64
import json
import os
from collections.abc import Sequence
from typing import Any

import httpx
from loguru import logger


class AITunnelAPIError(RuntimeError):
    """Ошибка, которую вернул API AITunnel."""

    def __init__(
        self,
        status_code: int,
        message: str,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(f"AITunnel API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.metadata = metadata


class AIService:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.aitunnel.ru/v1/",
        timeout: float = 600.0,
    ):
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate_image(
        self,
        prompt: str,
        image_name: str,
        model: str = "gemini-3.1-flash-image",
        reference_image: bytes | Sequence[bytes] | None = None,
        aspect_ratio: str | None = None,
    ) -> tuple[str, float | None]:
        reference_images = self._normalize_reference_images(reference_image)
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if reference_images:
            payload["input_references"] = [
                self._build_image_reference(image) for image in reference_images
            ]

        logger.info(
            f"Генерация изображения [{image_name}]: "
            f"референсов={len(reference_images)}, "
            f"aspect_ratio={aspect_ratio or 'не указан'}"
        )

        try:
            data = await self._post("images/generations", payload)
            images = data.get("data")
            if not isinstance(images, list) or not images:
                raise ValueError("AITunnel вернул пустой список изображений")

            first_image = images[0]
            if not isinstance(first_image, dict):
                raise ValueError("AITunnel вернул изображение в неизвестном формате")

            image_data = first_image.get("b64_json")
            if not isinstance(image_data, str) or not image_data:
                logger.warning(f"AITunnel не вернул b64_json: {data}")
                raise ValueError("В ответе AITunnel отсутствуют данные изображения")

            path = self._save_image(image_data, image_name)
            if not path:
                raise RuntimeError(f"Не удалось сохранить изображение: {image_name}")

            return path, self._extract_cost_rub(data)
        except AITunnelAPIError as exc:
            if exc.status_code == 429:
                logger.warning(f"Превышены лимиты запросов AITunnel: {exc.message}")
            else:
                logger.error(
                    f"AITunnel ответил ошибкой {exc.status_code}: {exc.message}"
                )
            raise
        except httpx.HTTPError as exc:
            logger.error(f"Ошибка HTTP при обращении к AITunnel: {exc}")
            raise
        except Exception as exc:
            logger.exception(f"Непредвиденная ошибка генерации изображения: {exc}")
            raise

    async def generate_post(
        self,
        prompt: str,
        task_id: str,
        model: str = "gpt-4.1-nano",
    ) -> tuple[str, float | None]:
        payload = {
            "model": model,
            "messages": [
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
            "temperature": 0.8,
        }

        try:
            data = await self._post("chat/completions", payload)
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError("AITunnel вернул пустой список вариантов")

            choice = choices[0]
            if not isinstance(choice, dict):
                raise ValueError("AITunnel вернул вариант ответа в неизвестном формате")
            if choice_error := choice.get("error"):
                raise self._api_error(choice_error, fallback_status=502)

            message = choice.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str) or not content.strip():
                logger.warning(f"[{task_id}] Получено пустое сообщение от модели")
                raise ValueError("Модель сгенерировала пустой текст")

            return content, self._extract_cost_rub(data)
        except AITunnelAPIError as exc:
            if exc.status_code == 429:
                logger.warning(f"[{task_id}] Лимит запросов AITunnel исчерпан")
            else:
                logger.error(
                    f"[{task_id}] Ошибка AITunnel (Status: {exc.status_code}): "
                    f"{exc.message}"
                )
            raise
        except httpx.HTTPError as exc:
            logger.error(f"[{task_id}] Ошибка HTTP при обращении к AITunnel: {exc}")
            raise
        except Exception as exc:
            logger.exception(f"[{task_id}] Ошибка при генерации поста: {exc}")
            raise

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(endpoint, json=payload)
        return self._parse_response(response)

    @classmethod
    def _parse_response(cls, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            if response.is_error:
                message = response.text.strip() or response.reason_phrase
                raise AITunnelAPIError(response.status_code, message) from exc
            raise ValueError("AITunnel вернул некорректный JSON") from exc

        if not isinstance(data, dict):
            raise ValueError("AITunnel вернул ответ в неизвестном формате")

        if response.is_error or data.get("error"):
            raise cls._api_error(data.get("error"), response.status_code)

        return data

    @staticmethod
    def _api_error(error: Any, fallback_status: int) -> AITunnelAPIError:
        if isinstance(error, dict):
            raw_code = error.get("code", error.get("status", fallback_status))
            try:
                status_code = int(raw_code)
            except (TypeError, ValueError):
                status_code = fallback_status
            message = str(error.get("message") or "Неизвестная ошибка")
            metadata = error.get("metadata")
            if not isinstance(metadata, dict):
                metadata = None
            return AITunnelAPIError(status_code, message, metadata)

        message = str(error) if error else "Неизвестная ошибка"
        return AITunnelAPIError(fallback_status, message)

    @staticmethod
    def _extract_cost_rub(response: dict[str, Any]) -> float | None:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return None
        cost = usage.get("cost_rub")
        return cost if isinstance(cost, (int, float)) else None

    @staticmethod
    def _normalize_reference_images(
        reference_image: bytes | Sequence[bytes] | None,
    ) -> list[bytes]:
        if reference_image is None:
            return []
        if isinstance(reference_image, bytes):
            images = [reference_image]
        else:
            images = list(reference_image)

        if len(images) > 3:
            raise ValueError("Можно использовать не более 3 референсных изображений")
        if any(not isinstance(image, bytes) or not image for image in images):
            raise ValueError("Референсное изображение не должно быть пустым")
        return images

    @classmethod
    def _build_image_reference(cls, image: bytes) -> dict[str, Any]:
        image_b64 = base64.b64encode(image).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {
                "url": (
                    f"data:{cls._detect_image_media_type(image)};base64,{image_b64}"
                )
            },
        }

    @staticmethod
    def _detect_image_media_type(image: bytes) -> str:
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if image.startswith(b"RIFF") and image[8:12] == b"WEBP":
            return "image/webp"
        return "application/octet-stream"

    @staticmethod
    def _save_image(image_b64: str, image_name: str) -> str | None:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        try:
            directory = "media"
            os.makedirs(directory, exist_ok=True)

            try:
                img_data = base64.b64decode(image_b64, validate=True)
            except (ValueError, TypeError) as exc:
                logger.error(f"Ошибка валидации base64: {exc}")
                return None

            file_name = f"{image_name}.png"
            file_path = os.path.join(directory, file_name)
            with open(file_path, "wb") as img_file:
                img_file.write(img_data)

            logger.info(f"Изображение успешно сохранено: {file_path}")
            return file_name
        except PermissionError:
            logger.error(f"Ошибка доступа: нет прав на запись в директорию {directory}")
        except OSError as exc:
            logger.error(f"Ошибка ввода-вывода при сохранении {image_name}: {exc}")
        except Exception as exc:
            logger.exception(f"Непредвиденная ошибка в _save_image: {exc}")

        return None

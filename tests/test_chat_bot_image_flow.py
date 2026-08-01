import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

for name, value in {
    "VK_GROUP_TOKEN": "test",
    "VK_PROTECTED_KEY": "test",
    "VK_SERVICE_TOKEN": "test",
    "VK_GROUP_CONFIRMATION_TOKEN": "test",
    "AI_SERVICE_API_KEY": "test",
    "ADMIN_PASSWORD": "test",
    "VK_APP_ID": "1",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "GROUP_ID": "1",
}.items():
    os.environ.setdefault(name, value)

from app.database.models import GenerationType
from app.modules.chat_bot import handlers
from app.modules.chat_bot.keyboards import image_aspect_ratio_keyboard
from app.modules.chat_bot.states import UserState
from app.modules.chat_bot.utils import (
    extract_photo_urls,
    get_image_references,
    save_image_references,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.lists = {}

    async def delete(self, *keys) -> None:
        for key in keys:
            self.values.pop(key, None)
            self.lists.pop(key, None)

    async def get(self, key):
        return self.values.get(key)

    async def lrange(self, key, start, end):
        return list(self.lists.get(key, []))

    async def rpush(self, key, *values) -> None:
        self.lists.setdefault(key, []).extend(values)

    async def expire(self, key, ttl) -> None:
        return None


class ImageReferenceStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_references_can_be_added_sequentially_up_to_three(self) -> None:
        redis = FakeRedis()

        self.assertEqual(await save_image_references(7, [b"first"], redis), 1)
        self.assertEqual(
            await save_image_references(7, [b"second", b"third"], redis),
            3,
        )
        self.assertEqual(
            await get_image_references(7, redis),
            [b"first", b"second", b"third"],
        )

        with self.assertRaisesRegex(ValueError, "не более 3"):
            await save_image_references(7, [b"fourth"], redis)

    def test_extracts_all_photo_urls(self) -> None:
        attachments = [
            {
                "type": "photo",
                "photo": {
                    "sizes": [
                        {"url": "small", "width": 100, "height": 100},
                        {"url": "large", "width": 1000, "height": 800},
                    ]
                },
            },
            {"type": "doc", "doc": {}},
            {
                "type": "photo",
                "photo": {"photo_1280": "second-photo"},
            },
        ]

        self.assertEqual(extract_photo_urls(attachments), ["large", "second-photo"])


class ImageGenerationDialogTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_with_three_photos_opens_aspect_ratio_selection(self) -> None:
        redis = object()
        references = [b"first", b"second", b"third"]
        vk_client = SimpleNamespace(download=AsyncMock(side_effect=references))
        attachments = [
            {
                "type": "photo",
                "photo": {
                    "sizes": [
                        {
                            "url": f"photo-{index}",
                            "width": 1,
                            "height": 1,
                        }
                    ]
                },
            }
            for index in range(3)
        ]

        with (
            patch.object(
                handlers,
                "get_image_references",
                AsyncMock(return_value=[]),
            ),
            patch.object(
                handlers,
                "save_image_references",
                AsyncMock(return_value=3),
            ) as save_references,
            patch.object(handlers, "save_image_prompt", AsyncMock()) as save_prompt,
            patch.object(handlers, "set_user_state", AsyncMock()) as set_state,
            patch.object(handlers, "send_message", AsyncMock()) as send_message,
        ):
            await handlers.image_prompt_handler(
                7,
                "Нарисуй общий сюжет",
                vk_client,
                redis,
                object(),
                object(),
                attachments,
            )

        save_references.assert_awaited_once_with(7, references, redis)
        save_prompt.assert_awaited_once_with(7, "Нарисуй общий сюжет", redis)
        set_state.assert_awaited_once_with(
            7,
            UserState.AWAITING_IMAGE_ASPECT_RATIO,
            redis,
        )
        self.assertEqual(send_message.await_args.args[3], image_aspect_ratio_keyboard)

    async def test_selected_aspect_ratio_starts_generation(self) -> None:
        redis = object()
        references = [b"first", b"second", b"third"]

        with (
            patch.object(
                handlers,
                "get_image_prompt",
                AsyncMock(return_value="Нарисуй общий сюжет"),
            ),
            patch.object(
                handlers,
                "get_image_references",
                AsyncMock(return_value=references),
            ),
            patch.object(handlers, "clear_image_generation_context", AsyncMock()),
            patch.object(handlers, "set_user_state", AsyncMock()),
            patch.object(handlers, "_run_generation", AsyncMock()) as run_generation,
        ):
            await handlers.image_aspect_ratio_handler(
                7,
                "16:9",
                object(),
                redis,
                object(),
                object(),
            )

        run_generation.assert_awaited_once_with(
            7,
            "Нарисуй общий сюжет",
            GenerationType.IMAGE,
            unittest.mock.ANY,
            redis,
            unittest.mock.ANY,
            unittest.mock.ANY,
            reference_images=references,
            aspect_ratio="16:9",
        )


if __name__ == "__main__":
    unittest.main()

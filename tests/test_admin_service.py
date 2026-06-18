from datetime import datetime, timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.database.models import GenerationTask, GenerationType, TaskStatus, User
from app.modules.admin.service import get_user_details


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class GetUserDetailsTests(IsolatedAsyncioTestCase):
    async def test_returns_complete_generation_history(self):
        created_at = datetime(2026, 6, 18, 10, 30, tzinfo=timezone.utc)
        user = User(
            id=42,
            avatar="https://example.com/avatar.jpg",
            full_name="Иван Иванов",
            registered_at=created_at,
            last_balance_reset_at=created_at,
            is_donut=True,
            balance=17,
        )
        tasks = [
            GenerationTask(
                id="image-task",
                type=GenerationType.IMAGE,
                user_id=user.id,
                prompt="Нарисуй космодром",
                created_at=created_at,
                status=TaskStatus.SUCCESS,
                result="image-task.png",
                cost_rub=1.25,
            ),
            GenerationTask(
                id="post-task",
                type=GenerationType.POST,
                user_id=user.id,
                prompt="Напиши пост",
                created_at=created_at,
                status=TaskStatus.FAILED,
                result="Сервис недоступен",
                cost_rub=None,
            ),
        ]

        db = AsyncMock()
        db.get.return_value = user
        db.execute.side_effect = [_ScalarResult([]), _ScalarResult(tasks)]

        response = await get_user_details(db, user.id)

        self.assertEqual(len(response.generation_history), 2)

        image = response.generation_history[0]
        self.assertEqual(image.type, "image")
        self.assertEqual(image.status, "success")
        self.assertEqual(
            image.result,
            "https://vk.wonderrfau1t.site/images/image-task.png",
        )
        self.assertEqual(image.cost_rub, 1.25)
        self.assertIsNone(image.error)

        post = response.generation_history[1]
        self.assertEqual(post.type, "post")
        self.assertEqual(post.status, "failed")
        self.assertIsNone(post.result)
        self.assertEqual(post.error, "Сервис недоступен")

        payload = response.model_dump(by_alias=True, mode="json")
        self.assertIn("generationHistory", payload)
        self.assertEqual(payload["generationHistory"][0]["costRub"], 1.25)

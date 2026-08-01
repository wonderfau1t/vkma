import base64
import json
import os
import tempfile
import unittest

import httpx

from app.core.clients.aitunnel import AIService, AITunnelAPIError


class AIServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.service = AIService("test-api-key")
        await self.service.aclose()

    async def asyncTearDown(self) -> None:
        await self.service.aclose()

    def use_handler(self, handler) -> None:
        self.service._client = httpx.AsyncClient(
            base_url="https://api.aitunnel.ru/v1/",
            headers={"Authorization": "Bearer test-api-key"},
            transport=httpx.MockTransport(handler),
        )

    async def test_generate_post_uses_chat_completions(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer test-api-key")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "gpt-4.1-nano")
            self.assertEqual(payload["messages"][-1]["content"], "Напиши пост")
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Готовый пост"}}],
                    "usage": {"cost_rub": 0.42},
                },
            )

        self.use_handler(handler)
        content, cost = await self.service.generate_post("Напиши пост", "task-1")

        self.assertEqual(content, "Готовый пост")
        self.assertEqual(cost, 0.42)

    async def test_generate_image_sends_up_to_three_references(self) -> None:
        references = [
            b"\x89PNG\r\n\x1a\nfirst",
            b"\xff\xd8\xffsecond",
            b"RIFFxxxxWEBPthird",
        ]
        generated = b"generated-image"

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/images/generations")
            payload = json.loads(request.content)
            self.assertEqual(payload["aspect_ratio"], "16:9")
            data_urls = [
                item["image_url"]["url"] for item in payload["input_references"]
            ]
            self.assertEqual(len(data_urls), 3)
            self.assertEqual(
                data_urls,
                [
                    f"data:image/png;base64,{base64.b64encode(references[0]).decode('ascii')}",
                    f"data:image/jpeg;base64,{base64.b64encode(references[1]).decode('ascii')}",
                    f"data:image/webp;base64,{base64.b64encode(references[2]).decode('ascii')}",
                ],
            )
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"b64_json": base64.b64encode(generated).decode("ascii")}
                    ],
                    "usage": {"cost_rub": 3.4},
                },
            )

        self.use_handler(handler)
        previous_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            try:
                file_name, cost = await self.service.generate_image(
                    "Измени фото",
                    "task-2",
                    reference_image=references,
                    aspect_ratio="16:9",
                )
                with open(os.path.join("media", file_name), "rb") as image_file:
                    self.assertEqual(image_file.read(), generated)
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(file_name, "task-2.png")
        self.assertEqual(cost, 3.4)

    async def test_generate_image_rejects_more_than_three_references(self) -> None:
        with self.assertRaisesRegex(ValueError, "не более 3"):
            await self.service.generate_image(
                "Измени фото",
                "task-too-many",
                reference_image=[b"1", b"2", b"3", b"4"],
            )

    async def test_structured_api_error_is_preserved(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                json={
                    "error": {
                        "code": 429,
                        "message": "Rate limit exceeded",
                        "metadata": {"retry_after": 5},
                    }
                },
            )

        self.use_handler(handler)
        with self.assertRaises(AITunnelAPIError) as caught:
            await self.service.generate_post("Пост", "task-3")

        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.message, "Rate limit exceeded")
        self.assertEqual(caught.exception.metadata, {"retry_after": 5})


if __name__ == "__main__":
    unittest.main()

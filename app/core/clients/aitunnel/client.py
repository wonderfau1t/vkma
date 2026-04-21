import base64

from openai import AsyncOpenAI


class AIService:
    def __init__(self, api_key: str, base_url: str = "https://api.aitunnel.ru/v1/"):
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    async def aclose(self):
        await self._client.close()

    async def generate_image(
        self, prompt: str, image_name: str, model: str = "gemini-2.5-flash-image"
    ):
        response = await self._client.images.generate(model=model, prompt=prompt)
        if not response or not isinstance(response.data, list):
            raise ValueError("Пришел корявый ответ от сервиса генерации")

        image_b64 = response.data[0].url
        if not image_b64:
            raise ValueError("Нету ссылки в ответе")

        path = self._save_image(image_b64, image_name)
        if not path:
            raise ValueError("Ошибка при сохранении")

        return path

    async def generate_post(self, prompt: str, model: str = "gpt-4.1-nano"): ...

    def _save_image(self, image_b64: str, image_name: str):
        if "," in image_b64:
            image_b64 = image_b64.split(",")[1]
        try:
            # 3. Декодируем base64 в бинарные данные
            img_data = base64.b64decode(image_b64)

            # 4. Сохраняем в файл изображения
            with open(f"media/{image_name}.png", "wb") as img_file:
                img_file.write(img_data)

            return image_name + ".png"

        except Exception as e:
            print(f"Ошибка при декодировании: {e}")


# from app.core.config import settings

# client = OpenAI(
#     api_key=settings.ai_tunnel_api_key.get_secret_value(),
#     base_url="https://api.aitunnel.ru/v1/",
# )

# # Делаем запрос
# response = client.images.generate(
#     model="gemini-3.1-flash-image-preview",
#     prompt="Хорошее освещение, солнце бликует на камере. Нужно чтобы девушка стояла с хотдогом",
# )


# image_url = response.data[0].url

# with open("image_31flash_image_b64.txt", "w") as fh:
#     fh.write(image_url)

# print("Успешно записано!")

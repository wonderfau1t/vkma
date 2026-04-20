from openai import AsyncOpenAI


class AIService:
    def __init__(self, api_key: str, base_url: str = "https://api.aitunnel.ru/v1/"):
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    async def aclose(self):
        await self._client.close()

    async def generate_image(self, prompt: str, model: str = "gemini-2.5-flash-image"): ...

    async def generate_post(self, prompt: str, model: str = "gpt-4.1-nano"): ...


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

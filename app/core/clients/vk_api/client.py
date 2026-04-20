import httpx


class AsyncVKApiClient:
    def __init__(
        self,
        base_url: str = "https://api.vk.ru/method/",
        api_version: str = "5.199",
        api_keys: dict = {},
    ):
        self._client = httpx.AsyncClient(base_url=base_url)
        self._api_version = api_version
        self._api_keys = api_keys

    async def aclose(self):
        await self._client.aclose()

    async def get(self, endpoint: str, params: dict = {}, token: str | None = None) -> dict:
        params["v"] = self._api_version
        params["lang"] = "ru"
        params["access_token"] = token or self._api_keys[endpoint]

        response = await self._client.get(endpoint, params=params)
        response.raise_for_status()

        return response.json()

    async def post(self, endpoint: str, payload: dict = {}, token: str | None = None):
        payload["v"] = self._api_version
        payload["access_token"] = token or self._api_keys[endpoint]

        response = await self._client.post(endpoint, data=payload)
        response.raise_for_status()

        return response.json()

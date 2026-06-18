import httpx


class AsyncVKApiClient:
    def __init__(
        self,
        base_url: str = "https://api.vk.ru/method/",
        api_version: str = "5.199",
        api_keys: dict | None = None,
    ):
        self._client = httpx.AsyncClient(base_url=base_url)
        self._api_version = api_version
        self._api_keys = api_keys or {}

    async def aclose(self):
        await self._client.aclose()

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict:
        response.raise_for_status()
        data = response.json()
        if error := data.get("error"):
            raise RuntimeError(
                f"VK API error {error.get('error_code')}: {error.get('error_msg')}"
            )
        return data

    async def get(
        self, endpoint: str, params: dict | None = None, token: str | None = None
    ) -> dict:
        params = dict(params or {})
        params["v"] = self._api_version
        params["lang"] = "ru"
        params["access_token"] = token or self._api_keys[endpoint]

        response = await self._client.get(endpoint, params=params)
        return self._parse_response(response)

    async def post(
        self, endpoint: str, payload: dict | None = None, token: str | None = None
    ) -> dict:
        payload = dict(payload or {})
        payload["v"] = self._api_version
        payload["access_token"] = token or self._api_keys[endpoint]

        response = await self._client.post(endpoint, data=payload)
        return self._parse_response(response)

    async def download(self, url: str) -> bytes:
        response = await self._client.get(url)
        response.raise_for_status()
        return response.content

    async def upload_file(
        self,
        url: str,
        field_name: str,
        file_name: str,
        content: bytes,
        content_type: str,
    ) -> dict:
        response = await self._client.post(
            url,
            files={field_name: (file_name, content, content_type)},
        )
        response.raise_for_status()
        return response.json()

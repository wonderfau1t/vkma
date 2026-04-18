import requests


class VKApiClient:
    def __init__(self):
        self.api_version = "5.199"
        self.base_url = "https://api.vk.ru/method/"
        self.tokens = {}

    def get(self, endpoint: str, params: dict | None = None, token: str | None = None):
        params = params or {}
        params["v"] = self.api_version
        params["access_token"] = token or self.tokens[endpoint]
        url = self.base_url + endpoint

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, body: dict | None = None, token: str | None = None):
        body = body or {}
        body["v"] = self.api_version
        body["access_token"] = token or self.tokens[endpoint]
        url = self.base_url + endpoint

        response = requests.post(url, data=body)
        response.raise_for_status()
        return response.json()

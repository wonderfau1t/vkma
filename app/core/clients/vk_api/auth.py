import base64
import hashlib
import hmac
import json
from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings


def verify_launch_params(vk_params: dict) -> bool:
    if not vk_params or "sign" not in vk_params:
        return False

    secret_key = settings.vk_protected_key.get_secret_value()

    vk_subset = {k: v for k, v in vk_params.items() if k.startswith("vk_") and k != "sign"}
    sorted_params = sorted(vk_subset.items())
    query_string = urlencode(sorted_params, doseq=True)

    hmac_obj = hmac.new(secret_key.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256)
    computed_sign = base64.urlsafe_b64encode(hmac_obj.digest()).decode("utf-8").rstrip("=")
    return computed_sign == vk_params["sign"]


async def get_verified_vk_token(
    access_token: Annotated[str, Header(alias="X-VK-Access-Token")] = ...,
    vk_launch_params: Annotated[str, Header(alias="X-VK-Launch-Params")] = ...,
) -> str:
    print("Access_token: ", access_token)
    print("VK launch params: ", vk_launch_params)
    # Парсим launch params из json строки
    try:
        vk_params: dict = json.loads(vk_launch_params)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-VK-Launch-Params должен быть валидным JSON",
        )

    # Проверка подписи
    if not verify_launch_params(vk_params):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверная подпись VK launch params (sign)",
        )

    # Проверка access_token
    if not access_token or len(access_token.strip()) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Требуется X-VK-Access-Token"
        )

    # Проверка, что токен принадлежит этому пользователю
    vk_user_id = vk_params.get("vk_user_id")
    if not vk_user_id:
        raise HTTPException(400, "Отсутствует vk_user_id в launch params")

    try:
        import requests

        response = requests.get(
            "https://api.vk.ru/method/users.get",
            params={
                "access_token": access_token,
                "v": "5.199",
                "fields": "id",
            },
            timeout=5,
        )
        data = response.json()
        print(data)
        if "error" in data or not data.get("response"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный VK access_token"
            )
        if vk_user_id != data["response"]["items"][0]["id"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Чужой VK access_token"
            )
    except Exception:
        pass

    return access_token.strip()


VKVerifiedTokenDep = Annotated[str, Depends(get_verified_vk_token)]

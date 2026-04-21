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
    vk_launch_params: Annotated[str, Header(alias="X-VK-Launch-Params")],
) -> dict:
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
    return vk_params["vk_user_id"]


VKVerifiedTokenDep = Annotated[int, Depends(get_verified_vk_token)]

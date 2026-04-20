from fastapi import APIRouter, Depends

from app.core.clients import AsyncVKApiClient
from app.core.clients.vk_api.auth import VKVerifiedTokenDep
from app.dependencies import get_vk_client

from .service import build_analysis_response, fetch_group_analysis

router = APIRouter()


@router.get("/{group_id}")
async def analyze_group(group_id: str, vk_client: AsyncVKApiClient = Depends(get_vk_client)):
    group_info = await fetch_group_analysis(group_id, vk_client)
    if group_info is None:
        return {"error_message": "Невозможно провести аудит группы"}
    response = build_analysis_response(group_info)
    return response


@router.get("/test-token")
async def test_token(user_token: VKVerifiedTokenDep):
    print("Успешно получен токен: ", user_token)

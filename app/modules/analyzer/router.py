from fastapi import APIRouter

from app.core.clients.vk_api.auth import VKVerifiedTokenDep

from .models import APIResponse
from .service import generate_response, get_group_info

router = APIRouter()


@router.get("/{group_id}")
async def analyze_group(group_id: str, user_token: VKVerifiedTokenDep):
    group_info = get_group_info(group_id, user_token)
    if group_info is None:
        return {"error_message": "Невозможно провести аудит группы"}
    response: APIResponse = generate_response(group_info)
    return response.to_dict()


@router.get("/test-token")
async def test_token(user_token: VKVerifiedTokenDep):
    print("Успешно получен токен: ", user_token)

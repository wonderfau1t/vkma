from fastapi import APIRouter

router = APIRouter()


@router.get("/users")
async def get_users(): ...


@router.get("/users/{user_id}")
async def get_user(): ...

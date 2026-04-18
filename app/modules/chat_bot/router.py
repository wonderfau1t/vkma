from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.config import settings

from .handlers import handle_message

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=3)


@router.post("", response_class=PlainTextResponse)
async def vk_callback(request):
    data = request.data

    if data.get("type") == "confirmation":
        return settings.vk_group_confirmation_token.get_secret_value()

    elif data.get("type") == "message_new":
        user_id = data["object"]["message"]["from_id"]
        message_text = data["object"]["message"]["text"]
        attachments = data["object"]["message"]["attachments"]
        if attachments:
            executor.submit(handle_message, user_id, attachments[0]["link"]["url"])
        else:
            executor.submit(handle_message, user_id, message_text)
        return "ok"

from typing import Literal

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    type: Literal["image", "post"]
    prompt: str

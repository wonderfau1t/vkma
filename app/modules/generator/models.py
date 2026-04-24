from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    type: Literal["image", "post"]
    prompt: str
    aspect_ratio: str | None = None


class UpdateCostsRequest(BaseModel):
    image: int = Field(gt=0)
    post: int = Field(gt=0)

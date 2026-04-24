from typing import Literal

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    type: Literal["image", "post"]
    prompt: str


class UpdateCostsRequest(BaseModel):
    image: int = Field(gt=0)
    post: int = Field(gt=0)

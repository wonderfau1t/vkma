from redis.asyncio import Redis

from app.core.config import settings

REDIS_KEY_IMAGE = "cost:image"
REDIS_KEY_POST = "cost:post"
REDIS_KEY_BASE_TOKENS = "tokens:base"
REDIS_KEY_DONUT_TOKENS = "tokens:donut"


def get_default_costs() -> dict[str, int]:
    return {
        "image": settings.default_image_cost,
        "post": settings.default_post_cost,
        "base_tokens": settings.default_base_tokens,
        "donut_tokens": settings.default_donut_tokens,
    }


async def get_costs(redis: Redis) -> dict[str, int]:
    default_costs = get_default_costs()
    image, post, base_tokens, donut_tokens = await redis.mget(
        REDIS_KEY_IMAGE,
        REDIS_KEY_POST,
        REDIS_KEY_BASE_TOKENS,
        REDIS_KEY_DONUT_TOKENS,
    )
    return {
        "image": int(image) if image else default_costs["image"],
        "post": int(post) if post else default_costs["post"],
        "base_tokens": int(base_tokens) if base_tokens else default_costs["base_tokens"],
        "donut_tokens": int(donut_tokens) if donut_tokens else default_costs["donut_tokens"],
    }


async def set_costs(
    redis: Redis,
    image: int,
    post: int,
    base_tokens: int | None = None,
    donut_tokens: int | None = None,
) -> dict[str, int]:
    values = {REDIS_KEY_IMAGE: image, REDIS_KEY_POST: post}
    if base_tokens is not None:
        values[REDIS_KEY_BASE_TOKENS] = base_tokens
    if donut_tokens is not None:
        values[REDIS_KEY_DONUT_TOKENS] = donut_tokens

    await redis.mset(values)
    return await get_costs(redis)

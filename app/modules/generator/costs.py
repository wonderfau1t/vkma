from redis.asyncio import Redis

REDIS_KEY_IMAGE = "cost:image"
REDIS_KEY_POST = "cost:post"

DEFAULT_COSTS = {
    "image": 10,
    "post": 2,
}


async def get_costs(redis: Redis) -> dict[str, int]:
    image, post = await redis.mget(REDIS_KEY_IMAGE, REDIS_KEY_POST)
    return {
        "image": int(image) if image else DEFAULT_COSTS["image"],
        "post": int(post) if post else DEFAULT_COSTS["post"],
    }


async def set_costs(redis: Redis, image: int, post: int) -> None:
    await redis.mset({REDIS_KEY_IMAGE: image, REDIS_KEY_POST: post})

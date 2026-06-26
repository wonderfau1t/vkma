import asyncio
import uuid
from collections.abc import AsyncIterator, Collection
from contextlib import asynccontextmanager
from time import monotonic

from redis.asyncio import Redis

from .states import BotState


class StateLockTimeout(TimeoutError):
    pass


class StateRepository:
    _TRANSITION_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if not current then
    current = ARGV[3]
end

local matches = false
for index = 4, #ARGV do
    if current == ARGV[index] then
        matches = true
        break
    end
end

if not matches then
    return 0
end

if ARGV[1] == ARGV[3] then
    redis.call('DEL', KEYS[1])
else
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
end
return 1
"""

    _RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

    def __init__(
        self,
        redis: Redis,
        *,
        namespace: str = "user_state",
        state_ttl: int = 3600,
        lock_ttl: float = 30,
    ) -> None:
        if state_ttl <= 0:
            raise ValueError("state_ttl must be greater than zero")
        if lock_ttl <= 0:
            raise ValueError("lock_ttl must be greater than zero")

        self._redis = redis
        self._namespace = namespace
        self._state_ttl = state_ttl
        self._lock_ttl_ms = int(lock_ttl * 1000)

    async def get(self, user_id: int) -> BotState:
        value = await self._redis.get(self._state_key(user_id))
        if value is None:
            return BotState.IDLE

        if isinstance(value, bytes):
            value = value.decode("utf-8")

        try:
            return BotState(value)
        except ValueError:
            await self.clear(user_id)
            return BotState.IDLE

    async def set(
        self,
        user_id: int,
        state: BotState,
        *,
        ttl: int | None = None,
    ) -> None:
        if state == BotState.IDLE:
            await self.clear(user_id)
            return

        expires_in = ttl if ttl is not None else self._state_ttl
        if expires_in <= 0:
            raise ValueError("ttl must be greater than zero")
        await self._redis.set(self._state_key(user_id), state.value, ex=expires_in)

    async def clear(self, user_id: int) -> None:
        await self._redis.delete(self._state_key(user_id))

    async def transition(
        self,
        user_id: int,
        expected: BotState | Collection[BotState],
        target: BotState,
        *,
        ttl: int | None = None,
    ) -> bool:
        expected_states = (
            (expected,) if isinstance(expected, BotState) else tuple(expected)
        )
        if not expected_states:
            raise ValueError("expected states must not be empty")

        expires_in = ttl if ttl is not None else self._state_ttl
        if expires_in <= 0:
            raise ValueError("ttl must be greater than zero")

        result = await self._redis.eval(
            self._TRANSITION_SCRIPT,
            1,
            self._state_key(user_id),
            target.value,
            expires_in,
            BotState.IDLE.value,
            *(state.value for state in expected_states),
        )
        return bool(result)

    @asynccontextmanager
    async def lock(
        self,
        user_id: int,
        *,
        blocking_timeout: float = 1,
        retry_interval: float = 0.05,
    ) -> AsyncIterator[None]:
        if blocking_timeout < 0:
            raise ValueError("blocking_timeout must not be negative")
        if retry_interval <= 0:
            raise ValueError("retry_interval must be greater than zero")

        key = self._lock_key(user_id)
        token = uuid.uuid4().hex
        deadline = monotonic() + blocking_timeout

        while not await self._redis.set(
            key,
            token,
            nx=True,
            px=self._lock_ttl_ms,
        ):
            if monotonic() >= deadline:
                raise StateLockTimeout(
                    f"Could not acquire state lock for user {user_id}"
                )
            await asyncio.sleep(retry_interval)

        try:
            yield
        finally:
            await asyncio.shield(
                self._redis.eval(
                    self._RELEASE_LOCK_SCRIPT,
                    1,
                    key,
                    token,
                )
            )

    def _state_key(self, user_id: int) -> str:
        return f"{self._namespace}:{user_id}"

    def _lock_key(self, user_id: int) -> str:
        return f"{self._namespace}_lock:{user_id}"

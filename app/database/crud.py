from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import GenerationTask, GenerationType, TaskStatus, User


async def get_user_by_user_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_id: int) -> User:
    user = User(id=user_id, balance=30)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def activate_subscription(db: AsyncSession, user_id: int):
    user = await db.get(User, user_id)
    if not user:
        raise ValueError("User not found")


async def create_task(
    db: AsyncSession, task_id: str, type: GenerationType, user_id: int, prompt: str
):
    task = GenerationTask(id=task_id, type=type, user_id=user_id, prompt=prompt)
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return task


async def get_task_by_task_id(db: AsyncSession, task_id: str) -> GenerationTask | None:
    result = await db.execute(select(GenerationTask).where(GenerationTask.id == task_id))
    return result.scalar_one_or_none()


async def update_task(db: AsyncSession, task_id: str, status: TaskStatus, result: str):
    task = await db.get(GenerationTask, task_id)
    if not task:
        raise ValueError("Task not found")

    task.status = status
    task.result = result
    await db.commit()
    await db.refresh(task)


async def get_history_by_type(
    db: AsyncSession, task_type: GenerationType, user_id: int
) -> Sequence[GenerationTask]:
    query = (
        select(GenerationTask)
        .where(GenerationTask.type == task_type, GenerationTask.user_id == user_id)
        .order_by(GenerationTask.created_at.desc())
    )

    result = await db.execute(query)

    return result.scalars().all()

async def has_processing_tasks(db: AsyncSession, user_id: int) -> GenerationTask | None:
    query = (
        select(GenerationTask)
        .where(
            GenerationTask.user_id == user_id,
            GenerationTask.status == TaskStatus.PROCESSING
        )
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()
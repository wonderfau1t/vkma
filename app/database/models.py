import enum
from datetime import datetime
from typing import List

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GenerationType(str, enum.Enum):
    IMAGE = "image"
    POST = "post"


class TaskStatus(str, enum.Enum):
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    balance: Mapped[int]
    is_donut: Mapped[bool] = mapped_column(default=False)

    tasks: Mapped[List["GenerationTask"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id: Mapped[str] = mapped_column(primary_key=True)
    type: Mapped[GenerationType] = mapped_column(SQLEnum(GenerationType))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    prompt: Mapped[str] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PROCESSING)
    result: Mapped[str] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship(
        back_populates="tasks",
    )

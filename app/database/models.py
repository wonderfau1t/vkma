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


class ActionType(str, enum.Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    SET = "set"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    avatar: Mapped[str] = mapped_column(default="", server_default="")
    balance: Mapped[int]
    is_donut: Mapped[bool] = mapped_column(default=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_balance_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tasks: Mapped[List["GenerationTask"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    logs: Mapped[List["UserLogs"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserLogs(Base):
    __tablename__ = "user_operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[ActionType] = mapped_column(SQLEnum(ActionType))
    amount: Mapped[int]
    change: Mapped[str]
    comment: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(
        back_populates="logs",
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
    cost_rub: Mapped[float] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship(
        back_populates="tasks",
    )

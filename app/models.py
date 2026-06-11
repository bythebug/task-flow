from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(PyEnum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class TaskPriority(PyEnum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class PermissionLevel(PyEnum):
    view = "view"
    edit = "edit"
    delete = "delete"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")
    task_permissions = relationship("TaskPermission", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_users_email", "email"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.todo)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.medium)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="tasks")
    permissions = relationship("TaskPermission", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tasks_user_id", "user_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_user_status", "user_id", "status"),
    )


class TaskPermission(Base):
    __tablename__ = "task_permissions"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_level = Column(Enum(PermissionLevel), nullable=False, default=PermissionLevel.view)

    task = relationship("Task", back_populates="permissions")
    user = relationship("User", back_populates="task_permissions")

    __table_args__ = (
        Index("ix_task_permissions_task_id", "task_id"),
        Index("ix_task_permissions_user_id", "user_id"),
        # a user can only have one permission record per task
        Index("uq_task_permissions_task_user", "task_id", "user_id", unique=True),
    )

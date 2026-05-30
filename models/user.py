from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum, String, Integer, DateTime, SmallInteger, CHAR
import datetime
import enum
import uuid
from flask_login import UserMixin
from .base import Base


class UserRole(enum.Enum):
    admin = "admin"
    user = "user"


class User(UserMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.user)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now(datetime.UTC))
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

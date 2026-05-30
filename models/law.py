from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, DateTime, SmallInteger, ForeignKey, UniqueConstraint, CHAR, Date
from typing import Optional, List
import datetime
from .base import Base


class Law(Base):
    __tablename__ = "laws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    last_modified: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    norms: Mapped[List["Norm"]] = relationship("Norm", back_populates="law")


class Norm(Base):
    __tablename__ = "norms"
    __table_args__ = (UniqueConstraint("law_id", "number", name="unique_norm"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    law_id: Mapped[int] = mapped_column(Integer, ForeignKey("laws.id"), nullable=False)
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    number_raw: Mapped[Optional[str]] = mapped_column(String(50))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    content: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(500))
    last_seen: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    content_hash: Mapped[Optional[str]] = mapped_column(CHAR(64))
    is_stale: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    law: Mapped["Law"] = relationship("Law", back_populates="norms")

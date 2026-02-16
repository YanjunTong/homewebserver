"""SQLAlchemy model definitions for HomeMedia Hub."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class AlbumMediaLink(Base):
    """Many-to-many link table between albums and media."""

    __tablename__ = "album_media_links"

    album_id: Mapped[int] = mapped_column(ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), primary_key=True)


class Media(Base):
    """Media file metadata tracked by the system."""

    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(2048), unique=True, index=True, nullable=False)
    media_type: Mapped[MediaType] = mapped_column(SQLEnum(MediaType, name="media_type"), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    albums: Mapped[List["Album"]] = relationship(
        secondary="album_media_links",
        back_populates="media_items",
        lazy="selectin",
    )


class Album(Base):
    """Album metadata."""

    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    cover_image_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    media_items: Mapped[List[Media]] = relationship(
        secondary="album_media_links",
        back_populates="albums",
        lazy="selectin",
    )

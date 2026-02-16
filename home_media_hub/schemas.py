"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models import MediaType


class MediaCreate(BaseModel):
    """Schema used when ingesting media metadata during scanning."""

    filename: str
    file_path: str
    media_type: MediaType
    size: int
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    created_at: Optional[datetime] = None
    is_favorite: bool = False
    thumbnail_path: Optional[str] = None


class MediaResponse(BaseModel):
    """Schema returned by media APIs."""

    id: int
    filename: str
    file_path: str
    media_type: MediaType
    size: int
    width: Optional[int]
    height: Optional[int]
    duration: Optional[float]
    created_at: Optional[datetime]
    added_at: datetime
    is_favorite: bool
    thumbnail_path: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class AlbumCreate(BaseModel):
    """Schema used to create a new album."""

    name: str
    description: Optional[str] = None
    cover_image_path: Optional[str] = None


class AlbumResponse(BaseModel):
    """Schema returned by album APIs."""

    id: int
    name: str
    description: Optional[str]
    cover_image_path: Optional[str]

    model_config = ConfigDict(from_attributes=True)

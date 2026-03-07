"""Pydantic v2 数据验证模式"""
from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class MediaType(str, Enum):
    """媒体类型枚举"""
    IMAGE = "image"
    VIDEO = "video"


# ==================== Media 相关 Schema ====================

class MediaCreate(BaseModel):
    """创建媒体请求模式"""
    album_id: int = Field(..., gt=0, description="所属相册 ID")
    filename: str = Field(..., min_length=1, max_length=255)
    file_path: str = Field(..., min_length=1, max_length=512)
    media_type: MediaType = Field(default=MediaType.IMAGE)
    size: int = Field(..., gt=0)
    width: Optional[int] = Field(default=None, ge=0)
    height: Optional[int] = Field(default=None, ge=0)
    duration: Optional[float] = Field(default=None, ge=0)
    is_favorite: bool = Field(default=False)
    thumbnail_path: Optional[str] = Field(default=None, max_length=512)


class MediaUpdate(BaseModel):
    """更新媒体请求模式"""
    filename: Optional[str] = Field(default=None, min_length=1, max_length=255)
    media_type: Optional[MediaType] = None
    width: Optional[int] = Field(default=None, ge=0)
    height: Optional[int] = Field(default=None, ge=0)
    duration: Optional[float] = Field(default=None, ge=0)
    is_favorite: Optional[bool] = None
    thumbnail_path: Optional[str] = Field(default=None, max_length=512)


class MediaRead(BaseModel):
    """媒体读取响应模式"""
    id: int
    album_id: int
    filename: str
    file_path: str
    media_type: MediaType
    size: int
    width: Optional[int]
    height: Optional[int]
    duration: Optional[float]
    created_at: datetime
    is_favorite: bool
    thumbnail_path: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class MediaDetailRead(MediaRead):
    """媒体详细信息读取响应模式（包含所属相册信息）"""
    album: Optional["AlbumRead"] = None

    model_config = ConfigDict(from_attributes=True)


# ==================== Album 相关 Schema ====================

class AlbumCreate(BaseModel):
    """创建相册请求模式 - 一个文件夹对应一个相册"""
    name: str = Field(..., min_length=1, max_length=255, description="相册名称（文件夹名称）")
    path: str = Field(..., min_length=1, max_length=512, description="文件夹绝对路径")
    cover_image_path: Optional[str] = Field(default=None, max_length=512, description="覆盖图片路径")


class AlbumUpdate(BaseModel):
    """更新相册请求模式"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    cover_image_path: Optional[str] = Field(default=None, max_length=512)


class AlbumRead(BaseModel):
    """相册读取响应模式"""
    id: int
    name: str
    path: str
    cover_image_path: Optional[str]
    cover_media_id: Optional[int] = None       # 封面媒体 ID（一次 JOIN 获取，省去前端额外请求）
    cover_media_type: Optional[str] = None     # 封面媒体类型（image/video）
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlbumDetailRead(AlbumRead):
    """相册详细信息读取响应模式（包含该相册中的所有媒体）"""
    media_items: List[MediaRead] = Field(default=[], description="该相册中的所有媒体文件")

    model_config = ConfigDict(from_attributes=True)


# 更新转发引用
MediaDetailRead.model_rebuild()
AlbumDetailRead.model_rebuild()


"""SQLAlchemy 模型定义"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Boolean,
    Float,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MediaType(str, Enum):
    """媒体类型枚举"""
    IMAGE = "image"
    VIDEO = "video"


class Album(Base):
    """
    相册模型 - 一个文件夹对应一个相册 (One Folder = One Album)
    
    关键特性：
    - 每个 Album 代表一个物理文件夹
    - path 是唯一的文件夹绝对路径
    - 与 Media 是一对多关系（One Album has Many Media）
    """
    __tablename__ = "album"

    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # 相册名称（文件夹名称）
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # 文件夹绝对路径（唯一）
    path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # 覆盖图片路径（文件夹中第一张图片，可为空）
    cover_image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    
    # 关系：一个 Album 有多个 Media
    media_items: Mapped[List["Media"]] = relationship(
        "Media",
        back_populates="album",
        cascade="all, delete-orphan",
    )


class Media(Base):
    """
    媒体文件模型 - 必须属于一个 Album
    
    关键特性：
    - 每个媒体文件都必须属于一个 Album（严格要求）
    - album_id 是外键，指向该文件所在的文件夹
    - 与 Album 是多对一关系（Many Media belong to One Album）
    """
    __tablename__ = "media"

    # 主键
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # 外键：所属的 Album
    album_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("album.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # 文件名
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # 文件路径（唯一）
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # 媒体类型（image/video）
    media_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MediaType.IMAGE.value,
    )
    
    # 文件大小（字节）
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # 宽度（图片/视频，可为空）
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # 高度（图片/视频，可为空）
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # 视频时长（秒，可为空）
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    
    # 是否收藏
    is_favorite: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    
    # 缩略图路径（可为空）
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # 关系：属于一个 Album
    album: Mapped["Album"] = relationship(
        "Album",
        back_populates="media_items",
    )

    __table_args__ = (
        Index("ix_media_album_id", "album_id"),
        Index("ix_media_media_type", "media_type"),
    )

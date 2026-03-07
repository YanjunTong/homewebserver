"""CRUD 操作 - 数据库增删改查辅助函数"""

from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from models import Album, Media, MediaType


# ==================== Album（相册）操作 ====================

async def get_album_by_id(db: AsyncSession, album_id: int) -> Optional[Album]:
    """根据ID获取相册"""
    stmt = select(Album).where(Album.id == album_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_album_by_path(db: AsyncSession, path: str) -> Optional[Album]:
    """根据文件夹路径获取相册"""
    stmt = select(Album).where(Album.path == path)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_all_albums(db: AsyncSession, skip: int = 0, limit: int = 20) -> List[tuple]:
    """获取所有相册（分页），一次 JOIN 返回封面 media_id 和 media_type，避免前端 N+1 请求"""
    # 子查询：每个相册中 id 最小的 media（用作封面）
    cover_media = aliased(Media)
    subq = (
        select(Media.album_id, func.min(Media.id).label("cover_media_id"))
        .group_by(Media.album_id)
        .subquery()
    )
    stmt = (
        select(Album, subq.c.cover_media_id, cover_media.media_type)
        .outerjoin(subq, Album.id == subq.c.album_id)
        .outerjoin(cover_media, cover_media.id == subq.c.cover_media_id)
        .offset(skip)
        .limit(limit)
        .order_by(Album.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.all()


async def count_albums(db: AsyncSession) -> int:
    """获取相册总数"""
    stmt = select(func.count(Album.id))
    result = await db.execute(stmt)
    return result.scalar() or 0


async def delete_album(db: AsyncSession, album_id: int) -> bool:
    """删除相册（级联删除所有媒体文件）"""
    album = await get_album_by_id(db, album_id)
    if not album:
        return False
    
    await db.delete(album)
    await db.commit()
    return True


# ==================== Media（媒体）操作 ====================

async def get_media_by_id(db: AsyncSession, media_id: int) -> Optional[Media]:
    """根据ID获取媒体文件"""
    stmt = select(Media).where(Media.id == media_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_media_by_path(db: AsyncSession, file_path: str) -> Optional[Media]:
    """根据文件路径获取媒体文件"""
    stmt = select(Media).where(Media.file_path == file_path)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_album_media(
    db: AsyncSession, 
    album_id: int, 
    skip: int = 0, 
    limit: int = 20
) -> List[Media]:
    """获取相册中的所有媒体文件（分页）"""
    stmt = (
        select(Media)
        .where(Media.album_id == album_id)
        .offset(skip)
        .limit(limit)
        .order_by(Media.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def count_album_media(db: AsyncSession, album_id: int) -> int:
    """获取相册中的媒体文件数量"""
    stmt = select(func.count(Media.id)).where(Media.album_id == album_id)
    result = await db.execute(stmt)
    return result.scalar() or 0


async def get_all_media(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 20,
    media_type: Optional[MediaType] = None
) -> List[Media]:
    """获取所有媒体文件（支持按类型过滤）"""
    stmt = select(Media)
    
    if media_type:
        stmt = stmt.where(Media.media_type == media_type)
    
    stmt = stmt.offset(skip).limit(limit).order_by(Media.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def count_media(db: AsyncSession, media_type: Optional[MediaType] = None) -> int:
    """获取媒体文件总数"""
    stmt = select(func.count(Media.id))
    
    if media_type:
        stmt = stmt.where(Media.media_type == media_type)
    
    result = await db.execute(stmt)
    return result.scalar() or 0


async def get_favorite_media(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 20
) -> List[Media]:
    """获取所有收藏的媒体文件"""
    stmt = (
        select(Media)
        .where(Media.is_favorite == True)
        .offset(skip)
        .limit(limit)
        .order_by(Media.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def toggle_favorite(db: AsyncSession, media_id: int) -> Optional[Media]:
    """切换媒体文件的收藏状态"""
    media = await get_media_by_id(db, media_id)
    if not media:
        return None
    
    media.is_favorite = not media.is_favorite
    await db.commit()
    return media


async def update_media_thumbnail(
    db: AsyncSession, 
    media_id: int, 
    thumbnail_path: str
) -> Optional[Media]:
    """更新媒体文件的缩略图路径"""
    media = await get_media_by_id(db, media_id)
    if not media:
        return None
    
    media.thumbnail_path = thumbnail_path
    await db.commit()
    return media


async def update_album_cover(
    db: AsyncSession, 
    album_id: int, 
    cover_image_path: str
) -> Optional[Album]:
    """更新相册封面"""
    album = await get_album_by_id(db, album_id)
    if not album:
        return None
    
    album.cover_image_path = cover_image_path
    await db.commit()
    return album


async def delete_media(db: AsyncSession, media_id: int) -> bool:
    """删除媒体文件记录"""
    media = await get_media_by_id(db, media_id)
    if not media:
        return False
    
    await db.delete(media)
    await db.commit()
    return True

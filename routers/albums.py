"""Album-related API routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import crud
from database import get_db
from models import Album
from schemas import AlbumRead, AlbumDetailRead, AlbumCreate
from services.scanner import scan_directory


router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("", response_model=List[AlbumRead])
async def get_albums(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取所有相册（分页），封面 media_id 通过 JOIN 一次查出，避免前端 N+1 请求"""
    rows = await crud.get_all_albums(db, skip=skip, limit=limit)
    return [
        AlbumRead(
            id=album.id,
            name=album.name,
            path=album.path,
            cover_image_path=album.cover_image_path,
            cover_media_id=cover_media_id,
            cover_media_type=str(cover_media_type) if cover_media_type else None,
            created_at=album.created_at,
        )
        for album, cover_media_id, cover_media_type in rows
    ]


@router.get("/count")
async def count_albums(db: AsyncSession = Depends(get_db)):
    """获取相册总数"""
    count = await crud.count_albums(db)
    return {"count": count}


@router.get("/{album_id}", response_model=AlbumDetailRead)
async def get_album(
    album_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取相册详情及其包含的所有媒体文件"""
    album = await crud.get_album_by_id(db, album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"相册 ID {album_id} 不存在"
        )
    
    return album


@router.delete("/{album_id}")
async def delete_album(
    album_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除相册（级联删除所有媒体文件）"""
    success = await crud.delete_album(db, album_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"相册 ID {album_id} 不存在"
        )
    
    return {"detail": "相册已删除"}


@router.get("/{album_id}/media")
async def get_album_media(
    album_id: int,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取相册中的所有媒体文件（分页）"""
    album = await crud.get_album_by_id(db, album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"相册 ID {album_id} 不存在"
        )
    
    media_list = await crud.get_album_media(db, album_id, skip=skip, limit=limit)
    return media_list


@router.get("/{album_id}/media/count")
async def count_album_media(
    album_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取相册中的媒体文件数量"""
    album = await crud.get_album_by_id(db, album_id)
    if not album:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"相册 ID {album_id} 不存在"
        )
    
    count = await crud.count_album_media(db, album_id)
    return {"count": count}

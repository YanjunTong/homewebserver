"""媒体文件扫描服务 - 基于目录的扫描"""
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

import ffmpeg
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Media, MediaType, Album
from config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm"}


async def get_image_dimensions(file_path: str) -> Optional[Tuple[int, int]]:
    """获取图像的尺寸（宽度, 高度）"""
    try:
        def _get_size():
            with Image.open(file_path) as img:
                return img.width, img.height
        
        size = await asyncio.to_thread(_get_size)
        return size
    except Exception as e:
        logger.warning(f"获取图像尺寸失败 {file_path}: {e}")
        return None


async def get_video_metadata(file_path: str) -> Optional[dict]:
    """获取视频的元数据（时长、尺寸）"""
    try:
        def _probe():
            return ffmpeg.probe(file_path)
        
        probe_data = await asyncio.to_thread(_probe)
        
        video_stream = None
        duration = None
        width = None
        height = None
        
        for stream in probe_data.get("streams", []):
            if stream["codec_type"] == "video":
                video_stream = stream
                break
        
        if video_stream:
            width = video_stream.get("width")
            height = video_stream.get("height")
        
        if "format" in probe_data:
            duration_str = probe_data["format"].get("duration")
            if duration_str:
                try:
                    duration = float(duration_str)
                except (ValueError, TypeError):
                    pass
        
        return {
            "duration": duration,
            "width": width,
            "height": height,
        }
    except Exception as e:
        logger.warning(f"获取视频元数据失败 {file_path}: {e}")
        return None


async def get_or_create_album(db: AsyncSession, folder_path: str) -> Optional[Album]:
    """根据文件夹路径获取或创建相册"""
    try:
        folder_path = os.path.abspath(folder_path)
        folder_name = os.path.basename(folder_path)
        
        stmt = select(Album).where(Album.path == folder_path)
        result = await db.execute(stmt)
        album = result.scalars().first()
        
        if album:
            return album
        
        album = Album(
            name=folder_name,
            path=folder_path,
            cover_image_path=None,
            created_at=datetime.utcnow(),
        )
        db.add(album)
        await db.flush()
        
        logger.info(f"创建新相册: {folder_name}")
        return album
        
    except Exception as e:
        logger.error(f"创建相册失败 {folder_path}: {e}")
        return None


async def scan_directory_based(db: AsyncSession, root_path: str = None) -> dict:
    """
    目录级相册扫描（递归）
    
    Step 1: 递归扫描 root_path 下所有子目录，创建/删除相册
    Step 2: 为每个相册扫描文件，添加/删除媒体
    """
    if root_path is None:
        root_path = settings.content_folder
    
    stats = {
        "albums_scanned": 0,
        "albums_created": 0,
        "albums_deleted": 0,
        "files_added": 0,
        "files_skipped": 0,
        "files_deleted": 0,
        "files_failed": 0,
        "errors": [],
    }
    
    if not os.path.isdir(root_path):
        error_msg = f"路径不存在或不是目录: {root_path}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        return stats
    
    try:
        # Step 1: 递归同步相册（文件夹）
        disk_folders = set()
        abs_root = os.path.abspath(root_path)
        
        for dirpath, dirnames, filenames in os.walk(root_path):
            abs_dir = os.path.abspath(dirpath)
            if abs_dir == abs_root:
                continue  # 跳过根目录本身，只扫描子目录
            disk_folders.add(abs_dir)
        
        logger.info(f"在磁盘上找到 {len(disk_folders)} 个文件夹")
        
        # 创建缺失的相册
        for folder_path in disk_folders:
            album = await get_or_create_album(db, folder_path)
            if album:
                if not album.id or album.id == 0:  # 新创建的
                    stats["albums_created"] += 1
            stats["albums_scanned"] += 1
        
        # 删除磁盘上不存在的相册
        stmt = select(Album).where(Album.path.like(f"{os.path.abspath(root_path)}%"))
        result = await db.execute(stmt)
        for album in result.scalars().all():
            if album.path not in disk_folders:
                logger.info(f"删除不存在的相册: {album.name}")
                await db.delete(album)
                stats["albums_deleted"] += 1
        
        await db.commit()
        
        # Step 2: 扫描每个相册中的文件
        stmt = select(Album).where(Album.path.like(f"{os.path.abspath(root_path)}%"))
        result = await db.execute(stmt)
        albums = result.scalars().all()
        
        for album in albums:
            album_stats = await scan_files_in_album(db, album)
            stats["files_added"] += album_stats["files_added"]
            stats["files_skipped"] += album_stats["files_skipped"]
            stats["files_deleted"] += album_stats["files_deleted"]
            stats["files_failed"] += album_stats["files_failed"]
            stats["errors"].extend(album_stats["errors"])
        
        logger.info(
            f"扫描完成 - 相册: 创建 {stats['albums_created']}, 删除 {stats['albums_deleted']}, "
            f"文件: 添加 {stats['files_added']}, 跳过 {stats['files_skipped']}, "
            f"删除 {stats['files_deleted']}, 失败 {stats['files_failed']}"
        )
        
    except Exception as e:
        error_msg = f"扫描时出错: {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        await db.rollback()
    
    return stats


async def scan_files_in_album(db: AsyncSession, album: Album) -> dict:
    """扫描相册文件夹内的媒体文件"""
    stats = {
        "files_added": 0,
        "files_skipped": 0,
        "files_deleted": 0,
        "files_failed": 0,
        "errors": [],
    }
    
    if not os.path.isdir(album.path):
        logger.warning(f"相册文件夹不存在: {album.path}")
        # 错误时不删除，只记录日志
        return stats
    
    try:
        # 获取磁盘上的文件
        disk_files: Dict[str, str] = {}  # file_path -> filename
        for filename in os.listdir(album.path):
            file_path = os.path.join(album.path, filename)
            if os.path.isfile(file_path):
                ext = Path(filename).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    disk_files[file_path] = filename
        
        # 从数据库获取已有的媒体
        stmt = select(Media).where(Media.album_id == album.id)
        result = await db.execute(stmt)
        db_medias = {media.file_path: media for media in result.scalars().all()}
        
        # 添加新文件
        for file_path, filename in disk_files.items():
            if file_path in db_medias:
                stats["files_skipped"] += 1
                continue
            
            try:
                file_stat = os.stat(file_path)
                file_size = file_stat.st_size
                created_time = datetime.fromtimestamp(file_stat.st_ctime)
                
                ext = Path(filename).suffix.lower()
                media_type = MediaType.IMAGE if ext in IMAGE_EXTENSIONS else MediaType.VIDEO
                
                width = None
                height = None
                duration = None
                
                if media_type == MediaType.IMAGE:
                    dims = await get_image_dimensions(file_path)
                    if dims:
                        width, height = dims
                
                else:  # VIDEO
                    meta = await get_video_metadata(file_path)
                    if meta:
                        width = meta.get("width")
                        height = meta.get("height")
                        duration = meta.get("duration")
                
                media = Media(
                    album_id=album.id,
                    filename=filename,
                    file_path=file_path,
                    media_type=media_type,
                    size=file_size,
                    width=width,
                    height=height,
                    duration=duration,
                    created_at=created_time,
                    is_favorite=False,
                    thumbnail_path=None,
                )
                
                db.add(media)
                stats["files_added"] += 1
                
                # 设置封面
                if media_type == MediaType.IMAGE and not album.cover_image_path:
                    album.cover_image_path = file_path
                
                logger.debug(f"添加: {filename}")
                
            except Exception as e:
                logger.error(f"处理 {filename} 失败: {e}")
                stats["files_failed"] += 1
                stats["errors"].append(str(e))
        
        # 删除不存在的文件
        for file_path, media in db_medias.items():
            if file_path not in disk_files:
                await db.delete(media)
                stats["files_deleted"] += 1
        
        await db.commit()
        
        if stats["files_added"] > 0:
            logger.info(f"相册 '{album.name}': 添加 {stats['files_added']} 文件")
        
    except Exception as e:
        logger.error(f"扫描相册 '{album.name}' 时出错: {e}")
        stats["errors"].append(str(e))
        await db.rollback()
    
    return stats


# 保留旧的 scan_directory 接口以兼容
async def scan_directory(root_path: str, db: AsyncSession) -> dict:
    """向后兼容的接口"""
    return await scan_directory_based(db, root_path)

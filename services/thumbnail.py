"""缩略图生成服务"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

import ffmpeg
from PIL import Image
from models import MediaType

logger = logging.getLogger(__name__)

# 缩略图存储目录
THUMBNAIL_DIR = Path(__file__).parent.parent / "static" / "thumbnails"
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

# 缩略图配置
THUMBNAIL_HEIGHT = 300
THUMBNAIL_FORMAT = "webp"
VIDEO_THUMBNAIL_TIMESTAMP = "00:00:05"


async def generate_image_thumbnail(file_path: str) -> Optional[str]:
    """
    生成图片缩略图
    
    Args:
        file_path: 原始图片路径
        
    Returns:
        缩略图相对路径（如 /static/thumbnails/xxx.webp）或 None 如果失败
    """
    try:
        file_name = Path(file_path).stem
        thumbnail_filename = f"{file_name}_thumb.{THUMBNAIL_FORMAT}"
        thumbnail_path = THUMBNAIL_DIR / thumbnail_filename
        
        # 如果缩略图已存在，直接返回
        if thumbnail_path.exists():
            logger.debug(f"缩略图已存在: {thumbnail_path}")
            return f"/static/thumbnails/{thumbnail_filename}"
        
        # 在线程中运行 Pillow 操作以防阻塞事件循环
        def _generate():
            with Image.open(file_path) as img:
                # 计算宽度以保持纵横比
                aspect_ratio = img.width / img.height
                new_width = int(THUMBNAIL_HEIGHT * aspect_ratio)
                
                # 缩放图片
                thumbnail = img.resize((new_width, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
                
                # 保存为 WebP 格式
                thumbnail.save(thumbnail_path, format="WebP", quality=80)
                logger.info(f"生成图片缩略图: {thumbnail_path}")
        
        await asyncio.to_thread(_generate)
        return f"/static/thumbnails/{thumbnail_filename}"
        
    except Exception as e:
        logger.warning(f"生成图片缩略图失败 {file_path}: {e}")
        return None


async def generate_video_thumbnail(file_path: str) -> Optional[str]:
    """
    生成视频缩略图 (使用 Intel VA-API 硬件加速)
    
    支持硬件加速：
    - Intel Quick Sync Video (VA-API) 通过 /dev/dri/renderD128
    - 硬件解码大大加速缩略图提取
    
    Args:
        file_path: 原始视频路径
        
    Returns:
        缩略图相对路径（如 /static/thumbnails/xxx.webp）或 None 如果失败
    """
    try:
        file_name = Path(file_path).stem
        thumbnail_filename = f"{file_name}_thumb.{THUMBNAIL_FORMAT}"
        thumbnail_path = THUMBNAIL_DIR / thumbnail_filename
        
        # 如果缩略图已存在，直接返回
        if thumbnail_path.exists():
            logger.debug(f"缩略图已存在: {thumbnail_path}")
            return f"/static/thumbnails/{thumbnail_filename}"
        
        # 在线程中运行 ffmpeg 操作以防阻塞事件循环
        def _generate():
            try:
                # 首先尝试使用硬件加速
                logger.info(f"尝试使用 VA-API 硬件加速生成缩略图: {file_path}")
                
                try:
                    # 使用 ffmpeg-python 库 + VA-API 硬件加速
                    # 这对 Intel CPU (Haswell 及以后) 有效
                    (
                        ffmpeg
                        .input(file_path, ss=5, hwaccel='vaapi', hwaccel_device='/dev/dri/renderD128')
                        .filter('scale', -1, THUMBNAIL_HEIGHT)
                        .output(str(thumbnail_path), vframes=1, format='image2')
                        .run(overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)
                    )
                    logger.info(f"✓ 使用硬件加速成功生成视频缩略图: {thumbnail_path}")
                    return
                    
                except Exception as hwaccel_error:
                    # 硬件加速失败，回退到软件解码
                    logger.warning(f"硬件加速失败 ({str(hwaccel_error)[:100]}...)，使用软件解码")
                    
                    (
                        ffmpeg
                        .input(file_path, ss=5)
                        .filter('scale', -1, THUMBNAIL_HEIGHT)
                        .output(str(thumbnail_path), vframes=1, format='image2')
                        .run(overwrite_output=True, quiet=True, capture_stdout=True, capture_stderr=True)
                    )
                    logger.info(f"使用软件解码生成视频缩略图: {thumbnail_path}")
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"ffmpeg 缩略图生成失败: {error_msg[:200]}")
                raise
        
        await asyncio.to_thread(_generate)
        
        # 检查文件是否成功生成
        if not thumbnail_path.exists():
            logger.warning(f"缩略图文件未生成: {thumbnail_path}")
            # 返回默认视频占位图 URL
            return "/static/video-placeholder.svg"
            
        return f"/static/thumbnails/{thumbnail_filename}"
        
    except Exception as e:
        logger.warning(f"生成视频缩略图失败 {file_path}: {e}")
        # 返回默认视频占位图 URL
        return "/static/video-placeholder.svg"


async def generate_thumbnail(file_path: str, media_type: str) -> Optional[str]:
    """
    生成缩略图（统一入口）
    
    Args:
        file_path: 媒体文件路径
        media_type: 媒体类型（'image' 或 'video'）
        
    Returns:
        缩略图 URL 或 None 如果失败
    """
    if not Path(file_path).exists():
        logger.warning(f"文件不存在: {file_path}")
        return None
    
    logger.info(f"开始生成缩略图: {file_path} ({media_type})")
    
    if media_type == "image":
        return await generate_image_thumbnail(file_path)
    elif media_type == "video":
        return await generate_video_thumbnail(file_path)
    else:
        logger.warning(f"未知的媒体类型: {media_type}")
        return None

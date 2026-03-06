"""媒体相关的 API 路由"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Media
from schemas import MediaRead, MediaDetailRead
from services.thumbnail import generate_thumbnail, THUMBNAIL_DIR, get_thumbnail_path
from services.streamer import range_requests_response

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/media", tags=["媒体"])


@router.get("", response_model=list[MediaRead])
async def list_media(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=5000, description="返回的最大记录数"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取媒体列表（分页）
    
    Args:
        skip: 分页偏移量
        limit: 分页大小
        
    Returns:
        媒体列表
    """
    try:
        stmt = select(Media).offset(skip).limit(limit)
        result = await db.execute(stmt)
        media_list = result.scalars().all()
        
        logger.info(f"获取媒体列表: skip={skip}, limit={limit}, count={len(media_list)}")
        return media_list
    except Exception as e:
        logger.error(f"获取媒体列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取媒体列表失败")


@router.get("/count")
async def get_media_count(db: AsyncSession = Depends(get_db)):
    """
    获取媒体总数
    
    Returns:
        媒体总数
    """
    try:
        from sqlalchemy import func
        stmt = select(func.count(Media.id))
        result = await db.execute(stmt)
        count = result.scalar() or 0
        
        logger.info(f"媒体总数: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"获取媒体总数失败: {e}")
        raise HTTPException(status_code=500, detail="获取媒体总数失败")


@router.get("/{media_id}", response_model=MediaDetailRead)
async def get_media_by_id(
    media_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    根据 ID 获取媒体详情
    
    Args:
        media_id: 媒体 ID
        
    Returns:
        媒体详情
    """
    try:
        stmt = select(Media).where(Media.id == media_id)
        result = await db.execute(stmt)
        media = result.scalars().first()
        
        if not media:
            raise HTTPException(status_code=404, detail="媒体不存在")
        
        logger.info(f"获取媒体详情: id={media_id}")
        return media
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取媒体详情失败: {e}")
        raise HTTPException(status_code=500, detail="获取媒体详情失败")


@router.get("/{media_id}/thumbnail")
async def get_media_thumbnail(
    media_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    获取媒体缩略图（直接返回图片文件）
    
    Args:
        media_id: 媒体 ID
        
    Returns:
        缩略图图片文件
    """
    try:
        # 获取媒体信息
        stmt = select(Media).where(Media.id == media_id)
        result = await db.execute(stmt)
        media = result.scalars().first()
        
        if not media:
            raise HTTPException(status_code=404, detail="媒体不存在")
        
        # 生成缩略图
        thumbnail_url = await generate_thumbnail(media.file_path, media.media_type)
        
        if thumbnail_url:
            # 检查是否是占位图 SVG
            if thumbnail_url.endswith(".svg"):
                # 返回 SVG 占位图
                svg_path = Path(__file__).parent.parent / "static" / "video-placeholder.svg"
                if svg_path.exists():
                    logger.info(f"返回视频占位图: {media_id}")
                    return FileResponse(
                        path=svg_path,
                        media_type="image/svg+xml",
                        headers={"Cache-Control": "no-cache"}
                    )
            
            # 正常缩略图处理
            # thumbnail_url 格式: /static/thumbnails/xxx.webp
            thumbnail_filename = thumbnail_url.split('/')[-1]
            thumbnail_file_path = Path(__file__).parent.parent / "static" / "thumbnails" / thumbnail_filename
            
            if thumbnail_file_path.exists():
                logger.info(f"返回缩略图文件: {thumbnail_file_path}")
                return FileResponse(
                    path=thumbnail_file_path,
                    media_type="image/webp",
                    headers={"Cache-Control": "no-cache"}
                )
        
        # 如果缩略图生成失败，返回一个占位符图片
        logger.warning(f"缩略图生成失败: {media_id}")
        raise HTTPException(status_code=500, detail="缩略图生成失败")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缩略图失败: {e}")
        raise HTTPException(status_code=500, detail="获取缩略图失败")


@router.get("/{media_id}/stream")
async def stream_media(
    media_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    流式传输媒体文件（支持范围请求）
    
    支持以下功能：
    - 断点续传
    - 随机播放（拖动进度条）
    - HTTP Range 请求
    
    Args:
        media_id: 媒体 ID
        request: FastAPI 请求对象
        
    Returns:
        StreamingResponse（流式分块传输）
    """
    try:
        # 获取媒体信息
        stmt = select(Media).where(Media.id == media_id)
        result = await db.execute(stmt)
        media = result.scalars().first()
        
        if not media:
            raise HTTPException(status_code=404, detail="媒体不存在")
        
        # 获取文件路径
        file_path = media.file_path
        
        # 视频使用流式传输（支持拖动进度条），图片直接返回原文件
        if media.media_type == "video":
            if file_path.endswith(".mp4"):
                content_type = "video/mp4"
            elif file_path.endswith(".mkv"):
                content_type = "video/x-matroska"
            else:
                content_type = "video/mp4"
            logger.info(f"流式传输视频: id={media_id}")
            return await range_requests_response(request, file_path, content_type)
        else:
            # 图片直接返回原文件，不分块，让浏览器完整缓存
            ext = Path(file_path).suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".gif": "image/gif",
                ".webp": "image/webp", ".bmp": "image/bmp",
            }
            content_type = mime_map.get(ext, "image/jpeg")
            logger.info(f"直接返回图片: id={media_id}")
            return FileResponse(
                path=file_path,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=3600"},
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"流式传输失败: {e}")
        raise HTTPException(status_code=500, detail="流式传输失败")


@router.post("/{media_id}/rotate")
async def rotate_image(
    media_id: int,
    direction: str = Query("cw", description="旋转方向: cw=顺时针90°, ccw=逆时针90°"),
    db: AsyncSession = Depends(get_db),
):
    """
    旋转图片并永久保存到磁盘，同时更新数据库中的宽高信息并清除缩略图缓存。

    Args:
        media_id: 媒体 ID
        direction: 旋转方向，cw=顺时针90°，ccw=逆时针90°
    """
    if direction not in ("cw", "ccw"):
        raise HTTPException(status_code=400, detail="direction 必须为 cw 或 ccw")

    stmt = select(Media).where(Media.id == media_id)
    result = await db.execute(stmt)
    media = result.scalars().first()

    if not media:
        raise HTTPException(status_code=404, detail="媒体不存在")

    if media.media_type != "image":
        raise HTTPException(status_code=400, detail="仅支持旋转图片文件")

    file_path = Path(media.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="图片文件不存在")

    # 执行旋转（Pillow transpose 不重新编码像素块，质量损失最低）
    # ROTATE_270 = 顺时针90°, ROTATE_90 = 逆时针90°
    transpose_op = (
        Image.Transpose.ROTATE_270 if direction == "cw" else Image.Transpose.ROTATE_90
    )

    def _rotate():
        with Image.open(str(file_path)) as img:
            # 先应用 EXIF 方向，再手动旋转，保证方向一致
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            rotated = img.transpose(transpose_op)
            suffix = file_path.suffix.lower()
            if suffix in (".jpg", ".jpeg"):
                rotated.save(str(file_path), format="JPEG", quality=95, subsampling=0)
            elif suffix == ".png":
                rotated.save(str(file_path), format="PNG")
            elif suffix == ".webp":
                rotated.save(str(file_path), format="WEBP", quality=95)
            else:
                rotated.save(str(file_path))
            return rotated.width, rotated.height

    try:
        new_width, new_height = await asyncio.to_thread(_rotate)
    except Exception as e:
        logger.error(f"旋转图片失败 {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"旋转图片失败: {e}")

    # 删除旧缩略图，让下次访问时重新生成
    thumb = get_thumbnail_path(str(file_path))
    try:
        thumb.unlink(missing_ok=True)
    except Exception:
        pass

    # 更新数据库中的宽高和缩略图路径
    media.width = new_width
    media.height = new_height
    media.thumbnail_path = None
    await db.commit()

    logger.info(f"图片旋转成功: id={media_id}, direction={direction}, size={new_width}x{new_height}")
    return {"status": "ok", "width": new_width, "height": new_height}

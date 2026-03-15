"""媒体相关的 API 路由"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Media, MediaType
from schemas import MediaRead, MediaDetailRead
from services.thumbnail import generate_thumbnail, THUMBNAIL_DIR, get_thumbnail_path
from services.streamer import (
    range_requests_response,
    stream_from_time,
)
from services.faststart import ensure_faststart
from services.faststart import FASTSTART_EXTS
from services.previewer import generate_video_preview, get_preview_path, PREVIEW_DIR

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/media", tags=["媒体"])


@router.post("/faststart/generate-missing", tags=["媒体"])
async def generate_missing_faststart(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """后台为所有支持 faststart 的视频生成缓存，避免首次播放等待。"""
    stmt = select(Media).where(Media.media_type == MediaType.VIDEO)
    result = await db.execute(stmt)
    videos = result.scalars().all()

    targets = [m for m in videos if Path(m.file_path).suffix.lower() in FASTSTART_EXTS]
    if not targets:
        return {"queued": 0, "message": "无可处理的 MP4/MOV/M4V"}

    async def _build_all():
        from services.faststart import ensure_faststart
        for m in targets:
            try:
                await ensure_faststart(m.file_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("faststart 预生成失败 id=%s err=%s", m.id, exc)

    background_tasks.add_task(_build_all)
    logger.info("faststart 预生成任务已启动，待处理 %d 个文件", len(targets))
    return {"queued": len(targets), "message": "预生成任务已启动"}


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
                        headers={"Cache-Control": "public, max-age=3600"}
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
                    headers={"Cache-Control": "public, max-age=86400, immutable"}
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
    start: float | None = Query(default=None, ge=0, description="起播时间（秒）"),
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
            ext = Path(file_path).suffix.lower()
            video_mime_map = {
                ".mp4":  "video/mp4",
                ".mkv":  "video/x-matroska",
                ".avi":  "video/x-msvideo",
                ".mov":  "video/quicktime",
                ".webm": "video/webm",
                ".flv":  "video/x-flv",
                ".wmv":  "video/x-ms-wmv",
                ".m4v":  "video/x-m4v",
            }
            content_type = video_mime_map.get(ext, "video/mp4")

            # 直接指定 start 参数：精准起播
            if start is not None:
                logger.info("直起播 stream_from_time: id=%s start=%.2f", media_id, start)
                return await stream_from_time(file_path, start, content_type)

            # 默认：faststart + Range
            stream_path = await ensure_faststart(file_path)
            content_type = video_mime_map.get(Path(stream_path).suffix.lower(), "video/mp4")
            logger.info(
                "流式传输视频: id=%s path=%s faststart=%s",
                media_id,
                Path(stream_path).name,
                stream_path != file_path,
            )
            return await range_requests_response(request, stream_path, content_type)
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


# ==================== 预览视频接口 ====================

@router.get("/{media_id}/preview")
async def get_media_preview(
    media_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    获取视频预览片段（60s 精彩合集，无声 MP4）。

    若预览文件已生成则直接流式返回；
    若尚未生成且视频足够长则同步生成后返回；
    若视频太短则返回 404。
    """
    stmt = select(Media).where(Media.id == media_id)
    result = await db.execute(stmt)
    media = result.scalars().first()

    if not media:
        raise HTTPException(status_code=404, detail="媒体不存在")
    if media.media_type != MediaType.VIDEO:
        raise HTTPException(status_code=400, detail="仅视频支持预览")

    preview_file = get_preview_path(media.file_path)

    # 已有缓存文件，直接流式返回
    if preview_file.exists():
        return await range_requests_response(request, str(preview_file), "video/mp4")

    # 取视频时长（优先用 DB 中记录的值）
    duration = media.duration
    if not duration:
        raise HTTPException(status_code=404, detail="无法获取视频时长")

    from services.previewer import MIN_DURATION
    if duration < MIN_DURATION:
        raise HTTPException(status_code=404, detail="视频过短，无预览")

    # 同步生成预览
    preview_url = await generate_video_preview(media.file_path, duration)
    if not preview_url:
        raise HTTPException(status_code=500, detail="预览生成失败")

    # 更新数据库
    media.preview_path = preview_url
    await db.commit()

    return await range_requests_response(request, str(preview_file), "video/mp4")


@router.post("/previews/generate-missing", tags=["媒体"])
async def generate_missing_previews(
    background_tasks: BackgroundTasks,
    min_duration: float = Query(120.0, ge=60, description="最短视频时长（秒），低于此值跳过"),
    db: AsyncSession = Depends(get_db),
):
    """
    后台批量生成缺失的视频预览。
    符合条件（视频类型 + 时长足够 + 预览文件不存在）的视频将进入后台队列生成。
    """
    stmt = select(Media).where(
        Media.media_type == MediaType.VIDEO,
        Media.duration >= min_duration,
    )
    result = await db.execute(stmt)
    videos = result.scalars().all()

    pending = [
        m for m in videos
        if not get_preview_path(m.file_path).exists()
    ]

    if not pending:
        return {"message": "所有符合条件的视频已有预览", "queued": 0}

    async def _batch_generate():
        """后台逐个生成，避免同时并发过多 FFmpeg 进程"""
        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as sess:
            for m in pending:
                try:
                    url = await generate_video_preview(m.file_path, m.duration)
                    if url:
                        # 更新 DB
                        db_media = await sess.get(Media, m.id)
                        if db_media:
                            db_media.preview_path = url
                            await sess.commit()
                except Exception as e:
                    logger.error(f"批量预览生成异常 media_id={m.id}: {e}")

    background_tasks.add_task(_batch_generate)
    logger.info(f"批量预览任务已启动，待处理 {len(pending)} 个视频")
    return {"message": "预览生成任务已启动", "queued": len(pending)}


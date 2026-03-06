"""FastAPI 应用主入口"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, Depends, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_db, close_db, get_db, engine
from services.scanner import scan_directory
from schemas import MediaRead, AlbumRead
from config import settings, ensure_folders_exist
from routers import media as media_router
from routers import albums as albums_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理
    - 启动时：初始化数据库，创建所有表
    - 关闭时：关闭数据库连接
    """
    # 启动事件
    logger.info("应用启动中...")
    logger.info(f"应用版本: {settings.app_name} v{settings.app_version}")
    
    try:
        # 初始化配置文件夹
        ensure_folders_exist()
        logger.info(f"图片文件夹: {settings.image_folder}")
        logger.info(f"视频文件夹: {settings.video_folder}")
        
        # 初始化数据库
        await init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise
    
    yield
    
    # 关闭事件
    logger.info("应用关闭中...")
    try:
        await close_db()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"数据库关闭失败: {e}")


# ==================== FastAPI 应用初始化 ====================

app = FastAPI(
    title="HomeMedia Hub",
    description="本地媒体库管理系统",
    version="1.0.0",
    lifespan=lifespan,
)


# ==================== 静态文件挂载 ====================

# 确保 static 目录存在
static_dir = Path(__file__).parent / "static"
if not static_dir.exists():
    static_dir.mkdir(exist_ok=True)
    logger.info(f"创建静态文件目录: {static_dir}")

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ==================== 注册路由器 ====================

app.include_router(media_router.router)
app.include_router(albums_router.router)


# ==================== 根路由 ====================

@app.get("/", tags=["系统"])
async def root():
    """根路由 - 重定向到首页"""
    return RedirectResponse(url="/static/index.html")


# ==================== Health Check ====================

@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "应用正常运行"}


# ==================== 扫描 API ====================

@app.api_route("/scan", methods=["GET", "POST"], tags=["扫描"])
async def scan_media(
    root_path: str = Query(None, description="要扫描的根目录路径（留空则使用配置默认值）"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """
    扫描指定目录下的媒体文件
    
    支持 GET 和 POST 请求方法
    
    Args:
        root_path: 目录路径（例如 /home/user/media），留空则使用配置文件中的值
        
    Returns:
        扫描状态消息
        
    注意：扫描在后台运行
    """
    # 如果没有提供路径，则使用配置的默认值
    if not root_path:
        root_path = settings.image_folder
    
    # 验证路径
    if not os.path.isdir(root_path):
        return {
            "status": "error",
            "message": f"路径不存在或不是目录: {root_path}"
        }
    
    # 添加后台任务
    background_tasks.add_task(scan_directory, root_path, db)
    
    logger.info(f"扫描任务已添加到后台队列: {root_path}")
    return {
        "status": "started",
        "message": f"开始扫描目录: {root_path}",
        "root_path": root_path,
    }


@app.api_route("/scan/images", methods=["GET", "POST"], tags=["扫描"])
async def scan_images(
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """
    快捷扫描：扫描配置中的图片文件夹
    
    支持 GET 和 POST 请求方法
    
    Returns:
        扫描状态消息
    """
    image_folder = settings.image_folder
    
    if not os.path.isdir(image_folder):
        return {
            "status": "error",
            "message": f"图片文件夹不存在: {image_folder}"
        }
    
    background_tasks.add_task(scan_directory, image_folder, db)
    
    logger.info(f"开始扫描图片文件夹: {image_folder}")
    return {
        "status": "started",
        "message": f"开始扫描图片文件夹: {image_folder}",
        "folder": image_folder,
    }


@app.api_route("/scan/videos", methods=["GET", "POST"], tags=["扫描"])
async def scan_videos(
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """
    快捷扫描：扫描配置中的视频文件夹
    
    支持 GET 和 POST 请求方法
    
    Returns:
        扫描状态消息
    """
    video_folder = settings.video_folder
    
    if not os.path.isdir(video_folder):
        return {
            "status": "error",
            "message": f"视频文件夹不存在: {video_folder}"
        }
    
    background_tasks.add_task(scan_directory, video_folder, db)
    
    logger.info(f"开始扫描视频文件夹: {video_folder}")
    return {
        "status": "started",
        "message": f"开始扫描视频文件夹: {video_folder}",
        "folder": video_folder,
    }


# ==================== 缩略图预生成 API ====================

@app.post("/thumbnails/generate-missing", tags=["缩略图"])
async def generate_missing_thumbnails(
    media_type: str = Query("all", pattern="^(all|image|video)$", description="媒体类型"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """
    预生成缺失的缩略图（在后台运行）
    
    用于首次加载页面时批量生成缺失的缩略图，加快后续加载速度
    
    Args:
        media_type: 媒体类型（all/image/video），默认为 all
        
    Returns:
        预生成状态消息
    """
    async def _generate_thumbnails():
        try:
            from models import Media
            from services.thumbnail import generate_thumbnail
            from sqlalchemy import select
            
            # 查询所有媒体
            if media_type in ["all", "image"]:
                stmt = select(Media).where(Media.media_type == "image")
            elif media_type == "video":
                stmt = select(Media).where(Media.media_type == "video")
            else:
                stmt = select(Media)
            
            result = await db.execute(stmt)
            media_list = result.scalars().all()
            
            generated_count = 0
            failed_count = 0
            
            logger.info(f"开始预生成缺失的缩略图，共 {len(media_list)} 个文件")
            
            for media in media_list:
                try:
                    # 生成缩略图
                    thumbnail_url = await generate_thumbnail(media.file_path, media.media_type)
                    if thumbnail_url:
                        generated_count += 1
                except Exception as e:
                    logger.warning(f"生成缩略图失败 {media.file_path}: {e}")
                    failed_count += 1
            
            logger.info(f"缩略图预生成完成：成功 {generated_count}，失败 {failed_count}")
            
        except Exception as e:
            logger.error(f"批量生成缩略图失败: {e}")
    
    background_tasks.add_task(_generate_thumbnails)
    
    logger.info(f"缩略图预生成任务已添加到后台队列 ({media_type})")
    return {
        "status": "started",
        "message": f"开始预生成 {media_type} 的缺失缩略图，请稍候...",
        "media_type": media_type,
    }




@app.get("/media", response_model=list[MediaRead], tags=["媒体"])
async def list_media(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回的最大记录数"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取媒体列表（带分页）
    
    Args:
        skip: 分页偏移量（默认 0）
        limit: 分页大小（默认 20，最大 100）
        
    Returns:
        媒体列表
    """
    try:
        from models import Media
        
        # 构建查询语句：获取总数和分页数据
        stmt = select(Media).offset(skip).limit(limit)
        result = await db.execute(stmt)
        media_list = result.scalars().all()
        
        logger.info(f"获取媒体列表: skip={skip}, limit={limit}, count={len(media_list)}")
        return media_list
    except Exception as e:
        logger.error(f"获取媒体列表失败: {e}")
        return []


@app.get("/media/count", tags=["媒体"])
async def get_media_count(db: AsyncSession = Depends(get_db)):
    """
    获取媒体总数
    
    Returns:
        媒体总数
    """
    try:
        from models import Media
        
        stmt = select(func.count(Media.id))
        result = await db.execute(stmt)
        count = result.scalar() or 0
        
        logger.info(f"媒体总数: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"获取媒体总数失败: {e}")
        return {"count": 0}


@app.get("/media/{media_id}", response_model=MediaRead, tags=["媒体"])
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
        from models import Media
        
        stmt = select(Media).where(Media.id == media_id)
        result = await db.execute(stmt)
        media = result.scalars().first()
        
        if not media:
            return {"detail": "媒体不存在"}
        
        logger.info(f"获取媒体详情: id={media_id}")
        return media
    except Exception as e:
        logger.error(f"获取媒体详情失败: {e}")
        return {"detail": "获取失败"}


# ==================== 相册 API (预留) ====================

@app.get("/albums", response_model=list[AlbumRead], tags=["相册"])
async def list_albums(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回的最大记录数"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取相册列表（带分页）
    
    Args:
        skip: 分页偏移量
        limit: 分页大小
        
    Returns:
        相册列表
    """
    try:
        from models import Album
        
        stmt = select(Album).offset(skip).limit(limit)
        result = await db.execute(stmt)
        albums = result.scalars().all()
        
        logger.info(f"获取相册列表: skip={skip}, limit={limit}, count={len(albums)}")
        return albums
    except Exception as e:
        logger.error(f"获取相册列表失败: {e}")
        return []


# ==================== 应用入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    # 在 localhost 的 8000 端口运行
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式自动重新加载
        reload_excludes=[
            "static/thumbnails/*",  # 排除缩略图缓存目录
            "**/__pycache__/*",      # 排除 Python 缓存
            "*.db",                  # 排除数据库文件
        ],
        log_level="info",
    )

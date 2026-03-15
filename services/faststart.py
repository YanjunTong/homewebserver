"""确保长视频支持快速随机跳转（moov 前置）

对于 MP4/MOV/M4V，如果 moov 原子在文件尾部，浏览器需要读取前序数据才能计算时间轴，
导致从第 1 分钟跳到第 3 分钟时要等中间数据下载完。这里用 ffmpeg 无损复制并加上
`-movflags +faststart`，把 moov 移到文件头，缓存后续直接复用。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# 仅对以下容器做 faststart 处理
FASTSTART_EXTS: Final = {".mp4", ".mov", ".m4v"}

# 缓存目录：static/faststart/
FASTSTART_DIR = Path(__file__).parent.parent / "static" / "faststart"
FASTSTART_DIR.mkdir(parents=True, exist_ok=True)


async def ensure_faststart(file_path: str) -> str:
    """
    返回可流式随机跳转的文件路径；必要时生成 faststart 缓存。

    - 非 MP4/MOV/M4V 直接返回原始路径
    - 缓存命名包含源文件绝对路径哈希 + mtime，文件变化会自动重建
    """

    src = Path(file_path)
    ext = src.suffix.lower()
    if ext not in FASTSTART_EXTS:
        logger.debug("faststart skip (ext=%s): %s", ext, src)
        return file_path
    if not src.exists():
        logger.warning("faststart skip (missing): %s", src)
        return file_path

    # 用绝对路径 + mtime_ns 做缓存键，文件变化自动失效
    key = hashlib.md5(str(src.resolve()).encode()).hexdigest()[:16]
    mtime_ns = src.stat().st_mtime_ns
    cached = FASTSTART_DIR / f"{key}_{mtime_ns}.mp4"

    if cached.exists():
        logger.info("faststart cache hit: %s", cached.name)
        return str(cached)

    # 清理旧版本缓存
    for old in FASTSTART_DIR.glob(f"{key}_*.mp4"):
        try:
            old.unlink()
        except OSError:
            pass

    logger.info("faststart build: %s -> %s", src.name, cached.name)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "0",
        str(cached),
    ]

    def _run() -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0:
                logger.warning(
                    "faststart 生成失败 code=%s file=%s err=%s",
                    result.returncode,
                    src,
                    result.stderr.decode(errors="replace")[-500:],
                )
                return False
            return True
        except FileNotFoundError:
            logger.error("ffmpeg 未找到，faststart 无法生成，请安装 ffmpeg")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning("faststart 生成异常 file=%s err=%s", src, exc)
            return False

    ok = await asyncio.to_thread(_run)
    if ok and cached.exists():
        logger.info("faststart ready: %s (%d KB)", cached.name, cached.stat().st_size // 1024)
        return str(cached)

    # 失败则回退原文件，并清理残留
    try:
        cached.unlink(missing_ok=True)
    except OSError:
        pass
    logger.info("faststart 回退原文件: %s", src)
    return file_path
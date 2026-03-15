"""视频预览（精彩片段合集）生成服务

生成逻辑：
- 仅处理时长 > 120 秒的视频
- 从视频的 5%~95% 区间均匀采样 20 个片段，每段 3 秒，合计约 60 秒
- 输出无声 MP4（libx264 faststart），分辨率缩放到高度 270px
- 文件名由原始路径 MD5 决定，存储于 static/previews/
"""

import asyncio
import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 预览视频存储目录
PREVIEW_DIR = Path(__file__).parent.parent / "static" / "previews"
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

# 生成参数
MIN_DURATION = 120       # 短于此时长（秒）的视频不生成预览
CLIP_COUNT = 20          # 片段数量
CLIP_DURATION = 3        # 每段时长（秒）
TARGET_HEIGHT = 270      # 输出高度（宽度按比例缩放，保持偶数）
START_RATIO = 0.05       # 跳过片头比例
END_RATIO = 0.95         # 跳过片尾比例


def get_preview_path(file_path: str) -> Path:
    """根据文件路径生成唯一预览视频路径（MD5 命名，与 thumbnail 服务一致）"""
    path_hash = hashlib.md5(file_path.encode()).hexdigest()[:16]
    return PREVIEW_DIR / f"{path_hash}_preview.mp4"


def _build_ffmpeg_preview_cmd(
    input_path: str,
    output_path: str,
    duration: float,
) -> list[str]:
    """
    构建单条 FFmpeg 命令，通过 concat filter 合并多个片段。
    使用多个 -ss/-t/-i 输入 + concat 滤镜，一次调用完成所有工作。
    """
    usable_start = duration * START_RATIO
    usable_end = duration * END_RATIO
    usable_range = usable_end - usable_start

    actual_clips = min(CLIP_COUNT, max(1, int(usable_range / CLIP_DURATION)))
    interval = usable_range / actual_clips

    cmd = ["ffmpeg", "-y"]

    # 每个片段：精确 seek 后读取 CLIP_DURATION 秒
    for i in range(actual_clips):
        seek_time = usable_start + i * interval
        cmd += ["-ss", f"{seek_time:.3f}", "-t", str(CLIP_DURATION), "-i", input_path]

    # 构建 filter_complex：统一缩放 + concat
    # scale 保持宽高比，高度固定为 TARGET_HEIGHT，宽对齐偶数
    scale_filter = f"scale=-2:{TARGET_HEIGHT}"
    filter_parts = []
    for i in range(actual_clips):
        filter_parts.append(f"[{i}:v]{scale_filter}[v{i}]")

    concat_inputs = "".join(f"[v{i}]" for i in range(actual_clips))
    filter_parts.append(f"{concat_inputs}concat=n={actual_clips}:v=1:a=0[out]")

    filter_complex = ";".join(filter_parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-an",                       # 无音频
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "28",
        "-movflags", "+faststart",
        "-loglevel", "error",
        output_path,
    ]
    return cmd


async def generate_video_preview(file_path: str, duration: float) -> Optional[str]:
    """
    生成视频预览片段。

    Args:
        file_path: 原始视频绝对路径
        duration:  视频时长（秒）

    Returns:
        预览视频 URL（如 /static/previews/xxx_preview.mp4），失败则返回 None
    """
    if duration < MIN_DURATION:
        logger.debug(f"视频过短（{duration:.0f}s），跳过预览生成: {file_path}")
        return None

    preview_path = get_preview_path(file_path)

    if preview_path.exists():
        logger.debug(f"预览已存在: {preview_path}")
        return f"/static/previews/{preview_path.name}"

    if not os.path.exists(file_path):
        logger.warning(f"原始视频不存在: {file_path}")
        return None

    cmd = _build_ffmpeg_preview_cmd(str(file_path), str(preview_path), duration)

    def _run() -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode != 0:
                logger.warning(
                    f"FFmpeg 预览生成失败 (code={result.returncode}) {file_path}:\n"
                    f"{result.stderr.decode(errors='replace')[-500:]}"
                )
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.warning(f"FFmpeg 预览生成超时: {file_path}")
            return False

    try:
        success = await asyncio.to_thread(_run)
        if success and preview_path.exists():
            size_kb = preview_path.stat().st_size // 1024
            logger.info(f"✓ 预览生成完成 ({size_kb} KB): {preview_path.name}")
            return f"/static/previews/{preview_path.name}"
        else:
            # 清理可能不完整的文件
            if preview_path.exists():
                preview_path.unlink(missing_ok=True)
            return None
    except Exception as e:
        logger.error(f"预览生成异常 {file_path}: {e}")
        if preview_path.exists():
            preview_path.unlink(missing_ok=True)
        return None


async def delete_video_preview(file_path: str) -> bool:
    """删除指定视频的预览文件"""
    preview_path = get_preview_path(file_path)
    if preview_path.exists():
        try:
            preview_path.unlink()
            logger.info(f"删除预览: {preview_path.name}")
            return True
        except OSError as e:
            logger.warning(f"删除预览失败: {e}")
    return False

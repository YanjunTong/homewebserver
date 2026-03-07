"""HTTP 范围请求流式传输服务"""
import logging
import os
from pathlib import Path
from typing import Tuple

from fastapi import Request
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

# 流式传输配置
# 远程访问优化：512KB 块大小，让视频更快开始播放（低带宽 Tailscale 连接）
CHUNK_SIZE = 1024 * 512  # 512KB 每个块


def parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    """
    解析 HTTP Range 头
    
    Args:
        range_header: Range 头值（如 "bytes=0-1000"）
        file_size: 文件总大小
        
    Returns:
        (start, end) 元组
    """
    try:
        # 处理 "bytes=start-end" 格式
        if not range_header.startswith("bytes="):
            return 0, file_size - 1
        
        range_str = range_header[6:]  # 移除 "bytes="
        
        if "-" not in range_str:
            return 0, file_size - 1
        
        parts = range_str.split("-")
        
        if len(parts) != 2:
            return 0, file_size - 1
        
        start_str, end_str = parts
        
        # 处理 "bytes=start-" (从 start 到末尾)
        if not end_str:
            start = int(start_str) if start_str else 0
            return start, file_size - 1
        
        # 处理 "bytes=start-end" (从 start 到 end)
        if start_str and end_str:
            start = int(start_str)
            end = int(end_str)
            return start, min(end, file_size - 1)
        
        # 处理 "bytes=-suffix" (最后 suffix 字节)
        if not start_str and end_str:
            suffix_length = int(end_str)
            start = max(0, file_size - suffix_length)
            return start, file_size - 1
        
        return 0, file_size - 1
        
    except (ValueError, IndexError):
        logger.warning(f"无效的 Range 头: {range_header}")
        return 0, file_size - 1


async def range_requests_response(
    request: Request,
    file_path: str,
    content_type: str = "video/mp4"
) -> StreamingResponse:
    """
    处理范围请求（支持随机播放和拖动进度条）
    
    Args:
        request: FastAPI 请求对象
        file_path: 文件路径
        content_type: 内容类型
        
    Returns:
        StreamingResponse 对象
    """
    # 获取文件大小
    try:
        file_size = os.path.getsize(file_path)
    except OSError as e:
        logger.error(f"无法获取文件大小 {file_path}: {e}")
        raise
    
    # 获取 Range 头
    range_header = request.headers.get("range")
    
    if range_header:
        # 解析 Range 请求
        start, end = parse_range_header(range_header, file_size)
        
        logger.info(f"范围请求: {start}-{end}/{file_size} from {request.client}")
        
        # 打开文件并读取指定范围
        async def iterate_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                
                while remaining > 0:
                    chunk_size = min(CHUNK_SIZE, remaining)
                    chunk = f.read(chunk_size)
                    
                    if not chunk:
                        break
                    
                    yield chunk
                    remaining -= len(chunk)
        
        # 返回 206 Partial Content 响应
        return StreamingResponse(
            iterate_file(),
            status_code=206,
            headers={
                "Content-Type": content_type,
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(end - start + 1),
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )
    else:
        # 完整文件请求
        logger.info(f"完整文件请求: {file_size} bytes from {request.client}")
        
        async def iterate_file():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
        
        # 返回 200 OK 响应
        return StreamingResponse(
            iterate_file(),
            status_code=200,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )

# 🎬 核心服务实现说明

## 📋 概述

本文档详细说明了 HomeMedia Hub 新增的三个核心模块：
1. **services/thumbnail.py** - 缩略图生成服务
2. **services/streamer.py** - HTTP 范围请求流式传输
3. **routers/media.py** - 媒体 API 路由

这三个模块完成了从"能扫描文件"到"能在浏览器看到图"的最后一公里。

---

## 1️⃣ 缩略图生成服务 (services/thumbnail.py)

### 💡 设计思路

**核心问题**：如果前端加载原始图片和视频，浏览器会卡死
- 一张 4K 照片可能 50MB+
- 一部 1080p 电影可能 2GB+
- 加载列表需要加载数百张原始文件？❌ 

**解决方案**：生成缩略图并缓存
- 图片：缩放到固定高度，转换为 WebP 格式
- 视频：提取第5秒的帧作为封面
- 一次生成，多次复用 ✅

### 🔧 核心函数

#### `generate_image_thumbnail(file_path: str) -> Optional[str]`

**功能**：为图片生成缩略图

**过程**：
```
1. 检查缓存 (/static/thumbnails/) 是否已有缩略图
   ├─ 有 → 直接返回路径
   └─ 无 → 继续
2. 使用 Pillow 打开图片
3. 计算宽度 = 高度 * 纵横比 (保持纵横比)
4. 使用 LANCZOS 算法缩放到 300px 高度
5. 转换为 WebP 格式，质量 80
6. 保存并返回 /static/thumbnails/xxxx_thumb.webp
```

**特性**：
- ✅ 在线程中运行，不阻塞事件循环
- ✅ 智能缓存，避免重复生成
- ✅ 支持多种图片格式 (jpg, png 等)

**示例**：
```python
thumbnail_url = await generate_image_thumbnail("/home/user/photo.jpg")
# 返回：/static/thumbnails/photo_thumb.webp
```

#### `generate_video_thumbnail(file_path: str) -> Optional[str]`

**功能**：为视频生成缩略图

**过程**：
```
1. 检查缓存
   ├─ 有 → 直接返回路径
   └─ 无 → 继续
2. 使用 ffmpeg 在时间戳 00:00:05 处提取一帧
3. 使用 scale filter 缩放到 300px 高度
4. 转换为 WebP 格式
5. 保存并返回访问 URL
```

**特性**：
- ✅ 在线程中运行 (`asyncio.to_thread`)
- ✅ 静默执行，不输出日志污染
- ✅ 支持多种视频格式 (mp4, mkv 等)

**示例**：
```python
thumb_url = await generate_video_thumbnail("/home/user/movie.mp4")
# 返回：/static/thumbnails/movie_thumb.webp
```

#### `generate_thumbnail(file_path: str, media_type: MediaType) -> Optional[str]`

**功能**：统一入口，根据媒体类型自动调用

**优势**：
```python
# 统一调用，无需判断类型
thumbnail_url = await generate_thumbnail(
    file_path="/home/user/media.mp4",
    media_type=MediaType.VIDEO
)
```

### ⚙️ 配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `THUMBNAIL_HEIGHT` | 300px | 缩略图目标高度 |
| `THUMBNAIL_FORMAT` | "webp" | 输出格式（WebP 更小） |
| `VIDEO_THUMBNAIL_TIMESTAMP` | "00:00:05" | 视频截图时间戳 |
| `THUMBNAIL_DIR` | `/static/thumbnails/` | 缓存目录 |

### 📂 输出示例

```
/home/yanjun/workspace/project/static/thumbnails/
├── photo1_thumb.webp     (15KB, 原图 5MB)
├── photo2_thumb.webp     (18KB, 原图 4MB)
├── movie_thumb.webp      (25KB, 第5秒截图)
└── ...
```

---

## 2️⃣ 流式传输服务 (services/streamer.py)

### 💡 设计思路

**核心问题**：浏览器无法拖动视频进度条
- 原因：必须等待整个文件下载完才能播放
- 没有 HTTP Range 支持 ❌

**解决方案**：实现 HTTP 206 Partial Content
- 支持 Range 请求
- 允许随机跳转播放
- 支持断点续传 ✅

### 🔧 核心函数

#### `parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]`

**功能**：解析 HTTP Range 头

**支持的 Range 格式**：

| 格式 | 含义 | 示例 |
|------|------|------|
| `bytes=0-1000` | 第 0 到 1000 字节 | `bytes=0-1000` |
| `bytes=1000-` | 第 1000 字节到末尾 | `bytes=1000-` |
| `bytes=-100` | 最后 100 字节 | `bytes=-100` |

**示例**：
```python
# 用户拖动进度条到 50% 位置
# 浏览器发送：Range: bytes=5242880-
start, end = parse_range_header("bytes=5242880-", 10485760)
# 返回：(5242880, 10485759)
```

#### `range_requests_response(request, file_path, content_type) -> StreamingResponse`

**功能**：处理流式传输和范围请求

**逻辑流程**：

```
请求到达
  │
  ├─ 有 Range 头？
  │  ├─ 是 → 解析 Range
  │  │      ├─ 打开文件
  │  │      ├─ Seek 到 start 位置
  │  │      ├─ 按块读取数据
  │  │      └─ 返回 206 Partial Content
  │  │
  │  └─ 否 → 完整传输
  │         ├─ 从文件开始读取
  │         ├─ 按块返回数据
  │         └─ 返回 200 OK
```

**返回头示例**：

```
Range 请求的响应头：
  HTTP/1.1 206 Partial Content
  Content-Range: bytes 0-1048575/10485760
  Content-Length: 1048576
  Accept-Ranges: bytes
  Content-Type: video/mp4

完整文件请求的响应头：
  HTTP/1.1 200 OK
  Content-Length: 10485760
  Accept-Ranges: bytes
  Content-Type: video/mp4
```

### 🎯 关键特性

| 特性 | 实现 |
|------|------|
| 分块传输 | 每块 1MB，内存占用低 |
| Range 支持 | 206 Partial Content |
| 断点续传 | 记住停止位置，继续传输 |
| 随机访问 | 任意位置播放视频 |
| 缓存控制 | Cache-Control: public, max-age=3600 |

### 📊 性能对比

| 场景 | 原始方案 | Range 方案 |
|------|---------|-----------|
| 播放 1GB 电影 | 必须下载全部 (1GB) | 仅下载已播放部分 |
| 拖动到 50% | 等待重新下载 50-100% | 直接跳转，无延迟 |
| 内存占用 | 可能 1GB | 恒定 1MB (块大小) |

---

## 3️⃣ 媒体路由 (routers/media.py)

### 📡 新增 API 端点

#### 1. 获取缩略图
```http
GET /media/{media_id}/thumbnail
```

**功能**：获取或生成媒体的缩略图

**请求**：
```bash
curl http://localhost:8000/media/1/thumbnail
```

**响应**：
```json
{
  "thumbnail_url": "/static/thumbnails/photo_thumb.webp",
  "message": "缩略图生成成功"
}
```

**流程**：
```
1. 查询数据库获取 Media 记录
2. 检查是否已有 thumbnail_path
   ├─ 有 → 直接返回
   └─ 无 → 调用生成函数
3. 如果生成成功，更新数据库
4. 返回缩略图 URL
```

**特性**：
- ✅ 第一次生成，之后查询缓存
- ✅ 自动更新数据库以备后用
- ✅ 返回有意义的错误消息

#### 2. 流式传输媒体
```http
GET /media/{media_id}/stream
```

**功能**：流式传输媒体文件，支持 Range 请求

**请求**：
```bash
# 完整传输
curl http://localhost:8000/media/1/stream

# Range 请求（拖动进度条到 50%）
curl -H "Range: bytes=5242880-" http://localhost:8000/media/1/stream
```

**响应**：
```
HTTP/1.1 206 Partial Content
Content-Type: video/mp4
Content-Range: bytes 5242880-10485759/10485760
Content-Length: 5242880
Accept-Ranges: bytes

[二进制视频数据块]
```

**流程**：
```
1. 查询数据库获取 Media 记录
2. 确定内容类型
   ├─ 视频 → video/mp4 或 video/x-matroska
   └─ 图片 → image/jpeg 或 image/png
3. 调用流式传输函数
4. 返回 StreamingResponse
```

**浏览器行为**：
```html
<!-- HTML video 标签 -->
<video controls width="100%">
  <source src="http://localhost:8000/media/1/stream" type="video/mp4">
</video>

<!-- 浏览器自动支持：-->
<!-- ✓ 拖动进度条 -->
<!-- ✓ 快进/快退 -->
<!-- ✓ 暂停/继续 -->
<!-- ✓ 音量调节 -->
```

### 🔄 完整工作流程示例

#### 场景：用户浏览媒体库

**步骤 1：列表页面加载**
```bash
GET /media?skip=0&limit=20
```
返回 20 条媒体信息

**步骤 2：前端请求缩略图**
```bash
GET /media/1/thumbnail
GET /media/2/thumbnail
...
GET /media/20/thumbnail
```
前端并行请求所有缩略图（加快加载）

**步骤 3：用户点击观看视频**
```bash
# 浏览器加载视频标签
<video src="http://localhost:8000/media/5/stream">
```

**步骤 4：用户拖动进度条到 2 分钟**
```bash
# 浏览器发送 Range 请求
Range: bytes=15728640-
```

**步骤 5：应用返回从指定位置开始的数据**
```
HTTP/1.1 206 Partial Content
Content-Range: bytes 15728640-...
```

### 📝 集成要点

#### 路由注册
```python
# main.py 中
from routers import media as media_router

app.include_router(media_router.router)
```

#### 前缀配置
```python
router = APIRouter(prefix="/media", tags=["媒体"])
# 所有端点都在 /media 前缀下
```

#### 依赖注入
```python
async def get_media_by_id(
    media_id: int,
    db: AsyncSession = Depends(get_db),  # 自动注入数据库会话
):
```

---

## 🎨 前端集成示例

### 媒体列表页面
```html
<div class="media-grid">
  <!-- 获取媒体列表 -->
  <script>
    fetch('/media?skip=0&limit=20')
      .then(r => r.json())
      .then(medias => {
        medias.forEach(media => {
          // 请求缩略图
          fetch(`/media/${media.id}/thumbnail`)
            .then(r => r.json())
            .then(data => {
              // 显示缩略图
              const img = document.createElement('img');
              img.src = data.thumbnail_url;
              document.body.appendChild(img);
            });
        });
      });
  </script>
</div>
```

### 视频播放页面
```html
<video width="100%" controls>
  <source src="/media/5/stream" type="video/mp4">
  您的浏览器不支持视频播放
</video>
```

---

## 🚀 性能考虑

### 缓存策略

**缩略图缓存**：
```
第 1 次请求 /media/1/thumbnail 
  ├─ 生成缩略图 (耗时 100-500ms)
  └─ 保存到 /static/thumbnails/

第 2 次请求 /media/1/thumbnail
  ├─ 直接返回已保存的路径 (< 1ms)
  └─ 从 disk 加载 WebP 文件 (快速)
```

**静态文件缓存**：
```
Cache-Control: public, max-age=3600
  └─ 浏览器缓存 1 小时，减少重复请求
```

### 网络优化

**流式传输优势**：
```
原始方案 (200MB 视频):
  下载时间：5分钟
  内存占用：200MB
  拖动延迟：5分钟（等待重新下载）

Range 方案:
  下载时间：取决于播放进度
  内存占用：常数 (1MB)
  拖动延迟：< 1 秒
```

---

## 🐛 错误处理

### 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| 404 文件不存在 | 媒体被删除 | 检查数据库 |
| 413 文件太大 | ffmpeg 无法处理 | 检查文件格式 |
| 416 Range 无效 | 字节范围超出 | 浏览器自动处理 |

### 日志记录
```python
logger.info(f"范围请求: {start}-{end}/{file_size} from {request.client}")
logger.warning(f"无效的 Range 头: {range_header}")
logger.error(f"流式传输失败: {e}")
```

---

## 📊 API 汇总

| 端点 | 方法 | 功能 | 新增 |
|------|------|------|------|
| `/media` | GET | 列表（分页） | ❌ |
| `/media/count` | GET | 总数 | ❌ |
| `/media/{id}` | GET | 详情 | ❌ |
| `/media/{id}/thumbnail` | GET | 缩略图 | ✅ |
| `/media/{id}/stream` | GET | 流式传输 | ✅ |

---

## 🎯 下一步工作

这三个模块完成后，你可以：

1. ✅ 生成图片和视频的缩略图
2. ✅ 在浏览器中预览和播放媒体
3. ✅ 支持拖动进度条和随机跳转
4. ⏭️ 开发前端 UI（HTML/CSS/JavaScript）
5. ⏭️ 添加搜索和筛选功能
6. ⏭️ 实现用户收藏和收藏夹功能

---

**创建日期**：2026-02-16  
**模块状态**：✅ 已完成  
**代码行数**：~600 行  
**功能关键字**：缩略图、范围请求、流式传输、缓存、性能优化

# 🔧 配置系统改进总结

## 问题回顾

**用户报告**：访问 `http://192.168.31.211:8000/` 返回 `{"detail":"Not Found"}` 错误

**原因分析**：
1. ✗ 根路由 `/` 未定义
2. ✗ 媒体文件夹路径没有配置管理
3. ✗ 扫描 API 没有默认路径支持

---

## ✅ 解决方案

### 1. 创建配置管理系统 (`config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 媒体文件夹
    image_folder: str = "/home/yanjun/media/images"
    video_folder: str = "/home/yanjun/media/videos"
    # 应用信息
    app_name: str = "HomeMedia Hub"
    debug: bool = True
```

**功能**：
- 从 `.env` 文件读取配置
- 自动创建不存在的文件夹（`ensure_folders_exist()`）
- 支持环境变量覆盖默认值

### 2. 创建 `.env` 配置文件

```env
IMAGE_FOLDER=/home/yanjun/media/images
VIDEO_FOLDER=/home/yanjun/media/videos
DEBUG=true
```

**配置位置**：
- 已添加到 `.gitignore`，不会被版本控制
- 应用启动时自动加载

### 3. 添加根路由 `GET /`

响应示例：
```json
{
  "app_name": "HomeMedia Hub",
  "version": "1.0.0",
  "status": "running",
  "media_config": {
    "image_folder": "/home/yanjun/media/images",
    "video_folder": "/home/yanjun/media/videos"
  },
  "api_endpoints": {
    "health_check": "GET /health",
    "scan_media": "POST /scan?root_path=/path/to/media",
    "list_media": "GET /media?skip=0&limit=20",
    ...
  }
}
```

**用途**：
- 获取应用信息
- 查看所有可用的 API 端点
- 检查配置的媒体文件夹

### 4. 增强扫描 API

#### 通用扫描（支持默认路径）
```bash
POST /scan?root_path=/custom/path    # 指定路径
POST /scan                           # 使用默认图片文件夹
```

#### 快捷扫描
```bash
POST /scan/images    # 扫描 IMAGE_FOLDER
POST /scan/videos    # 扫描 VIDEO_FOLDER
```

### 5. 生命周期改进 (`main.py`)

启动时自动执行：
```python
1. ✓ 初始化配置
2. ✓ 确保媒体文件夹存在
3. ✓ 初始化数据库
4. ✓ 输出配置信息
```

---

## 📂 文件结构

```
project/
├── main.py              # 主应用（已更新）
├── config.py            # 新增：配置管理
├── .env                 # 新增：环境变量
├── .env.example         # 新增：配置参考
├── README.md            # 已更新：详细说明
├── test_api.sh          # 新增：API 测试脚本
└── models.py            # 已修复：索引重复问题
```

---

## 🚀 快速开始

### 1. 修改 `.env` 文件

```bash
# 编辑配置
vim .env

# 修改以下部分：
IMAGE_FOLDER=/path/to/your/images
VIDEO_FOLDER=/path/to/your/videos
```

### 2. 启动应用

```bash
python main.py
```

输出示例：
```
✓ 文件夹已存在: /home/yanjun/media/images
✓ 文件夹已存在: /home/yanjun/media/videos
应用启动中...
应用版本: HomeMedia Hub v1.0.0
图片文件夹: /home/yanjun/media/images
视频文件夹: /home/yanjun/media/videos
数据库初始化完成
Application startup complete.
```

### 3. 访问 API

#### 获取应用信息
```bash
curl http://localhost:8000/
```

#### 扫描媒体（后台运行）
```bash
# 扫描图片
curl -X POST http://localhost:8000/scan/images

# 扫描视频
curl -X POST http://localhost:8000/scan/videos

# 扫描自定义路径
curl -X POST "http://localhost:8000/scan?root_path=/custom/path"
```

#### 查询媒体
```bash
# 获取列表
curl http://localhost:8000/media?skip=0&limit=20

# 获取总数
curl http://localhost:8000/media/count
```

---

## 🧪 测试结果

✅ 根路由测试：
```bash
$ curl http://localhost:8000/
{
  "app_name": "HomeMedia Hub",
  "status": "running",
  ...
}
```

✅ 健康检查：
```bash
$ curl http://localhost:8000/health
{
  "status": "ok",
  "message": "应用正常运行"
}
```

✅ 媒体计数：
```bash
$ curl http://localhost:8000/media/count
{
  "count": 0
}
```

---

## 🔧 配置选项

### 修改媒体文件夹

编辑 `.env` 文件：

```env
# 图片文件夹
IMAGE_FOLDER=/home/user/Pictures

# 视频文件夹
VIDEO_FOLDER=/home/user/Videos

# 调试模式
DEBUG=true
```

重启应用后生效。

### 添加新的文件夹

如需扫描多个文件夹，可修改 `config.py` 添加新字段：

```python
class Settings(BaseSettings):
    image_folder: str = "..."
    video_folder: str = "..."
    backup_folder: str = "..."  # 新增
```

然后在 `main.py` 中添加新的扫描端点：

```python
@app.post("/scan/backup")
async def scan_backup(...):
    ...
```

---

## 📋 环境变量完整列表

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `IMAGE_FOLDER` | 图片文件夹路径 | `/home/yanjun/media/images` |
| `VIDEO_FOLDER` | 视频文件夹路径 | `/home/yanjun/media/videos` |
| `APP_NAME` | 应用名称 | `HomeMedia Hub` |
| `DEBUG` | 调试模式 | `true` |
| `DATABASE_URL` | 数据库 URL | `sqlite+aiosqlite:///./media.db` |

---

## ✨ 完整的 API 路由列表

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/` | 获取应用信息 ✨ **新增** |
| GET | `/health` | 健康检查 |
| POST | `/scan` | 扫描指定路径（支持默认值） ✨ **改进** |
| POST | `/scan/images` | 快捷扫描图片文件夹 ✨ **新增** |
| POST | `/scan/videos` | 快捷扫描视频文件夹 ✨ **新增** |
| GET | `/media` | 获取媒体列表（分页） |
| GET | `/media/count` | 获取媒体总数 |
| GET | `/media/{id}` | 获取单个媒体详情 |
| GET | `/albums` | 获取相册列表（分页） |

---

## 🐛 注意事项

1. **`.env` 文件安全**
   - 包含本地路径和配置信息
   - 已添加到 `.gitignore`
   - 每个开发者需自己配置

2. **文件夹自动创建**
   - 应用启动时会检查并创建配置路径
   - 如果路径不存在，会自动创建
   - 如果路径无权限，会输出错误日志

3. **后台扫描**
   - 所有扫描操作都在后台运行
   - 不会阻塞 API 响应
   - 可通过日志查看扫描进度

---

## 总结

这次改进完全解决了用户的问题：

✅ 访问 `/` 返回应用信息，不再是 404
✅ 可在 `.env` 文件中配置媒体文件夹
✅ 提供了多种扫描方式（通用、快捷）
✅ 配置自动加载和文件夹自动创建
✅ 完整的 API 文档和使用说明

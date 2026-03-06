# HomeMedia Hub 快速开始指南

## 📋 项目配置

### 1. 配置媒体文件夹 (.env 文件)

编辑 `.env` 文件来配置您的媒体文件夹路径：

```env
# 图片文件夹路径
IMAGE_FOLDER=/home/yanjun/media/images

# 视频文件夹路径
VIDEO_FOLDER=/home/yanjun/media/videos

# 应用调试模式
DEBUG=true
```

**重要提示：** 
- 将 `/home/yanjun/media/images` 和 `/home/yanjun/media/videos` 替换为您实际的文件夹路径
- `.env` 文件已添加到 `.gitignore`，不会被版本控制
- 应用启动时会自动创建配置的文件夹（如果不存在）

## 🚀 运行应用

### 启动服务器

```bash
python main.py
```

应用将在 `http://0.0.0.0:8000` 上运行

### 访问 API 文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📡 API 端点

### 根路由
GET `/` - 获取应用信息和配置

**示例响应：**
```json
{
  "app_name": "HomeMedia Hub",
  "version": "1.0.0",
  "status": "running",
  "media_config": {
    "image_folder": "/home/yanjun/media/images",
    "video_folder": "/home/yanjun/media/videos"
  }
}
```

### 扫描 API

#### 1. 扫描指定路径
```
POST /scan?root_path=/your/media/path
```

#### 2. 快捷扫描图片（使用 .env 配置）
```
POST /scan/images
```

#### 3. 快捷扫描视频（使用 .env 配置）
```
POST /scan/videos
```

**响应示例：**
```json
{
  "status": "started",
  "message": "开始扫描目录: /home/yanjun/media/images",
  "folder": "/home/yanjun/media/images"
}
```

### 媒体 API

#### 获取媒体列表（分页）
```
GET /media?skip=0&limit=20
```

#### 获取媒体总数
```
GET /media/count
```

#### 获取单个媒体详情
```
GET /media/{media_id}
```

### 相册 API

#### 获取相册列表（分页）
```
GET /albums?skip=0&limit=20
```

## 💡 使用流程

1. **编辑 `.env` 文件**
   ```bash
   vim .env
   # 修改 IMAGE_FOLDER 和 VIDEO_FOLDER 路径
   ```

2. **启动应用**
   ```bash
   python main.py
   ```

3. **访问根路由获取信息**
   ```bash
   curl http://localhost:8000/
   ```

4. **扫描媒体文件**
   ```bash
   # 方式 1：扫描配置的图片文件夹
   curl -X POST http://localhost:8000/scan/images
   
   # 方式 2：扫描配置的视频文件夹
   curl -X POST http://localhost:8000/scan/videos
   
   # 方式 3：扫描任意路径
   curl -X POST "http://localhost:8000/scan?root_path=/custom/path"
   ```

5. **查询媒体**
   ```bash
   # 获取媒体列表
   curl http://localhost:8000/media?skip=0&limit=20
   
   # 获取媒体总数
   curl http://localhost:8000/media/count
   ```

## 🗂️ 文件结构

```
project/
├── main.py              # 应用主入口
├── database.py          # 数据库配置
├── models.py            # SQLAlchemy 模型
├── schemas.py           # Pydantic 验证模式
├── config.py            # 应用配置（新增）
├── .env                 # 环境变量配置（新增）
├── requirements.txt     # 依赖包列表
├── services/
│   ├── scanner.py       # 媒体扫描服务
│   ├── streamer.py
│   └── thumbnail.py
├── routers/
│   └── ...
└── static/              # 静态文件目录
```

## 📝 注意事项

- 扫描是在后台运行，不会阻塞 API
- 数据库文件 `media.db` 会自动创建在项目根目录
- 支持的图片格式：`.jpg`, `.jpeg`, `.png`
- 支持的视频格式：`.mp4`, `.mkv`
- 所有路径必须存在，否则会返回错误

## 🐛 常见问题

### "Not Found" 错误
- ✅ 确保访问了正确的 API 端点
- ✅ 访问 `/` 获取所有可用端点
- ✅ 访问 `/docs` 查看交互式 API 文档

### 为什么扫描后看不到文件？
- ✅ 扫描在后台运行，需要等待完成
- ✅ 检查查看日志确认扫描是否完成
- ✅ 使用 `/media/count` 检查数据库中的媒体数量

### 如何修改媒体文件夹？
- ✅ 编辑 `.env` 文件
- ✅ 重启应用
- ✅ 应用会自动创建不存在的文件夹

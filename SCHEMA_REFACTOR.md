# 📋 文件夹数据库架构重构 - 一个文件夹 = 一个相册

## 🎯 架构变更概述

系统已重构为**严格的"一个文件夹 = 一个相册"架构**，充分利用文件系统的物理结构。

---

## 📊 新架构设计

### 概念模型

```
文件系统                  数据库
==========              ==========

/media/
├── photos/              Album
│   ├── pic1.jpg   ---→  Media
│   ├── pic2.jpg   ---→  Media
│   └── pic3.jpg   ---→  Media
│
├── videos/              Album
│   ├── video1.mp4 ---→  Media
│   └── video2.mp4 ---→  Media
│
└── archive/             Album
    ├── photo1.jpg ---→  Media
    └── photo2.jpg ---→  Media
```

### 数据模型关系

#### 一对多关系（One-to-Many）

```
Album (相册 = 文件夹)
  ↓
  └─→ Media (媒体文件)
  └─→ Media (媒体文件)
  └─→ Media (媒体文件)
```

---

## 🗂️ 数据库表设计

### Album（相册表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AI | 主键 |
| `name` | VARCHAR(255) | NOT NULL, IDX | 相册名称（文件夹名） |
| `path` | VARCHAR(512) | NOT NULL, UNIQUE | 文件夹绝对路径 |
| `cover_image_path` | VARCHAR(512) | NULL | 封面图片路径（第一张图） |
| `created_at` | DATETIME | NOT NULL, IDX | 创建时间戳 |

**关键特性**：
- ✅ `path` 唯一约束：确保一个文件夹只对应一个相册
- ✅ 索引优化：`name` 和 `created_at` 用于查询优化
- ✅ 物理映射：直接对应文件系统的文件夹

### Media（媒体文件表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INT | PK, AI | 主键 |
| `album_id` | INT | FK, NOT NULL, IDX | ⚠️ **必须** 所属相册 |
| `filename` | VARCHAR(255) | NOT NULL | 文件名 |
| `file_path` | VARCHAR(512) | NOT NULL, UNIQUE, IDX | 文件绝对路径 |
| `media_type` | VARCHAR(50) | NOT NULL, IDX | image/video |
| `size` | INT | NOT NULL | 文件大小（字节） |
| `width` | INT | NULL | 宽度（像素） |
| `height` | INT | NULL | 高度（像素） |
| `duration` | FLOAT | NULL | 时长（秒，视频用） |
| `created_at` | DATETIME | NOT NULL, IDX | 上传时间 |
| `is_favorite` | BOOLEAN | NOT NULL, IDX | 收藏标记 |
| `thumbnail_path` | VARCHAR(512) | NULL | 缩略图路径 |

**关键特性**：
- ⚠️ `album_id` 必须不为空：每个文件都必须属于一个相册
- ✅ FK 约束：删除相册时级联删除媒体
- ✅ 完整的元数据：支持图片和视频

---

## 🔄 架构变更（旧 → 新）

### 删除的结构

❌ **album_media_association**（多对多关联表）
```
ALTER TABLE album_media_association DROP TABLE;
```

❌ **AlbumMediaLink**（关联模型）
```python
# 已删除
class AlbumMediaLink(Base):
    ...
```

❌ **Media.albums**（多对一关系）
```python
# 旧：
albums: Mapped[List["Album"]] = relationship(...)
```

❌ **Album.description**（描述字段）
```python
# 简化数据结构，移除不必要字段
```

### 新增的结构

✅ **Album.path**（文件夹路径）
```python
path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
```

✅ **Album.cover_image_path**（封面图片）
```python
cover_image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
```

✅ **Media.album_id**（强制外键）
```python
album_id: Mapped[int] = mapped_column(
    ForeignKey("album.id", ondelete="CASCADE"),
    nullable=False
)
```

✅ **Media.album**（关系映射）
```python
album: Mapped["Album"] = relationship("Album", back_populates="media_items")
```

---

## 📝 Schema 变更

### AlbumCreate（创建相册）

**旧**:
```json
{
  "name": "My Album",
  "description": "Album description"
}
```

**新**:
```json
{
  "name": "photos",
  "path": "/home/user/media/photos",
  "cover_image_path": "/home/user/media/photos/pic1.jpg"
}
```

### MediaCreate（创建媒体）

**旧**:
```json
{
  "filename": "photo.jpg",
  "file_path": "/path/to/photo.jpg",
  "media_type": "image",
  ...
}
```

**新**:
```json
{
  "album_id": 1,
  "filename": "photo.jpg",
  "file_path": "/path/to/photo.jpg",
  "media_type": "image",
  ...
}
```

### MediaDetailRead（媒体详情响应）

**旧**:
```json
{
  "id": 1,
  "filename": "photo.jpg",
  "albums": [...]
}
```

**新**:
```json
{
  "id": 1,
  "album_id": 5,
  "filename": "photo.jpg",
  "album": {
    "id": 5,
    "name": "photos",
    "path": "/path/to/photos",
    "cover_image_path": "...",
    "created_at": "2026-02-17T..."
  }
}
```

---

## 🚀 迁移步骤

### 步骤 1: 备份旧数据库
```bash
sqlite3 media.db ".backup media.db.backup.2026-02-17"
echo "✅ 备份完成"
```

### 步骤 2: 初始化新架构
```bash
# 方式 A: 自动创建（推荐）
cd /home/yanjun/workspace/project
python3 db_migrate.py migrate

# 方式 B: 删除旧数据库后重启应用
rm media.db
python main.py
# 应用启动时会自动创建新表结构
```

### 步骤 3: 验证架构
```bash
python3 db_migrate.py
```

输出示例：
```
相册（文件夹）数量: 0
媒体文件数量: 0

（首次扫描后会看到数据）
```

### 步骤 4: 重新扫描媒体
```bash
# 访问 API
curl -X POST http://localhost:8000/scan

# 或通过 UI 扫描
```

---

## 💡 使用示例

### 创建相册（文件夹）

```python
# Python 代码示例
async with AsyncSessionLocal() as session:
    album = Album(
        name="vacation_2025",
        path="/media/photos/vacation_2025",
        cover_image_path="/media/photos/vacation_2025/IMG_001.jpg"
    )
    session.add(album)
    await session.commit()
```

### 添加媒体到相册

```python
# 每个媒体必须指定 album_id
media = Media(
    album_id=album.id,  # 必须！
    filename="photo.jpg",
    file_path="/media/photos/vacation_2025/photo.jpg",
    media_type="image",
    size=2048576,
    ...
)
session.add(media)
await session.commit()
```

### 查询相册及其媒体

```python
# 获取相册及其所有媒体
album = await session.get(Album, album_id)
print(f"相册: {album.name}")
print(f"媒体数: {len(album.media_items)}")
for media in album.media_items:
    print(f"  - {media.filename}")
```

### 查询媒体的所属相册

```python
# 获取媒体及其所属相册
media = await session.get(Media, media_id)
print(f"媒体: {media.filename}")
print(f"所属相册: {media.album.name}")
```

---

## 🔍 数据库查询示例

### 查所有相册及其媒体统计
```sql
SELECT 
    a.id,
    a.name,
    a.path,
    COUNT(m.id) as media_count
FROM album a
LEFT JOIN media m ON a.id = m.album_id
GROUP BY a.id, a.name, a.path
ORDER BY a.created_at DESC;
```

### 查特定相册的所有媒体
```sql
SELECT * FROM media 
WHERE album_id = ? 
ORDER BY created_at DESC;
```

### 查某个文件夹的相册记录
```sql
SELECT * FROM album 
WHERE path = ? 
LIMIT 1;
```

### 查没有相册的孤立媒体（不应存在）
```sql
SELECT * FROM media 
WHERE album_id NOT IN (SELECT id FROM album);
```

---

## ✅ 验证清单

确保迁移后的数据完整性：

- [ ] ✅ Album 表有 path 和 cover_image_path 字段
- [ ] ✅ Media 表有 album_id 外键
- [ ] ✅ Media.album_id 不为空（所有媒体都有所属相册）
- [ ] ✅ Album.path 唯一（一个文件夹一个相册）
- [ ] ✅ 级联删除有效（删除相册时媒体被删除）
- [ ] ✅ 关系正确（一对多）
- [ ] ✅ 索引已建立（查询性能）

---

## 🎯 业务逻辑框架

### 扫描流程（新架构适配）

```
1. 发现文件夹 → 创建/获取 Album
2. 遍历文件夹内文件 → 为每个文件创建 Media (指定 album_id)
3. 第一张图片作为 cover_image_path
4. 其他非媒体文件忽略
```

### 查询流程

```
✅ 获取相册列表：SELECT * FROM album
✅ 获取相册中的媒体：SELECT * FROM media WHERE album_id = ?
✅ 获取媒体及其相册：SELECT * FROM media JOIN album WHERE media.album_id = album.id
```

---

## 🛡️ 数据完整性约束

| 约束 | 类型 | 说明 |
|------|------|------|
| `Album.path UNIQUE` | UNIQUE | 一个文件夹只能对应一个相册 |
| `Media.file_path UNIQUE` | UNIQUE | 一个文件只能入库一次 |
| `Media.album_id NOT NULL` | FK + NOT NULL | 每个文件必须属于一个相册 |
| ON DELETE CASCADE | 级联 | 删除相册时自动删除其媒体 |

---

## 📌 最佳实践

1. **始终指定 album_id**
   - 创建 Media 时必须提供有效的 album_id
   - 不要尝试创建没有相册的媒体

2. **维护路径唯一性**
   - 始终使用绝对路径作为 Album.path
   - 检查路径是否重复（避免误删）

3. **定期验证数据**
   ```bash
   python3 db_migrate.py
   ```

4. **备份重要数据**
   ```bash
   sqlite3 media.db ".backup media.db.backup.$(date +%Y%m%d_%H%M%S)"
   ```

---

## 🔧 故障排除

### 问题：Media 没有关联到 Album
```sql
-- 检查孤立媒体
SELECT COUNT(*) FROM media WHERE album_id IS NULL;
-- 应该返回 0
```

### 问题：相册重复
```sql
-- 检查重复的路径
SELECT path, COUNT(*) FROM album 
GROUP BY path 
HAVING COUNT(*) > 1;
-- 应该返回空结果集
```

### 问题：级联删除不工作
```python
# 确保 ForeignKey 定义正确
album_id: Mapped[int] = mapped_column(
    ForeignKey("album.id", ondelete="CASCADE"),  # ← ondelete="CASCADE"
    nullable=False
)
```

---

**✅ 架构重构完成！**

系统现已采用清晰的一对多关系，完全反映文件系统的物理结构。

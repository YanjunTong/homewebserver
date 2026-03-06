# 🚀 5分钟快速启动指南

> 数据库架构重构完成 ✅   
> 现在开始初始化应用

---

## 🎯 目标
启动应用、初始化新数据库架构、验证系统运行

## ⏱️ 预计时间
5-10分钟

---

## 📍 步骤 1: 停止现有应用

```bash
# 停止所有 Python 进程
pkill -f "python main"
pkill -f "uvicorn"

# 等待 1 秒确保完全退出
sleep 1
```

---

## 📍 步骤 2: 备份旧数据库（可选）

```bash
cd /home/yanjun/workspace/project

# 如果存在旧数据库，进行备份
if [ -f media.db ]; then
    cp media.db media.db.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ 数据库已备份"
fi
```

---

## 📍 步骤 3: 清除旧数据库（重要！）

```bash
# 删除旧数据库，强制创建新的
rm -f media.db

echo "✅ 已清除旧数据库"
```

---

## 📍 步骤 4: 启动应用

```bash
cd /home/yanjun/workspace/project

# 使用背景进程启动
nohup python main.py > app.log 2>&1 &

# 或使用前景启动（可观看日志）
# python main.py

echo "⏳ 等待应用启动..."
sleep 3
```

---

## 📍 步骤 5: 验证应用运行

### 方法 A: 检查进程

```bash
ps aux | grep "python main"
```

**预期输出**: 看到 `python main.py` 进程

### 方法 B: 检查日志

```bash
tail -20 app.log
```

**预期输出**:
```
INFO:     Started server process [XXXX]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 方法 C: 测试 API 接口

```bash
# 测试根路径（应该重定向到 /static/index.html）
curl -I http://localhost:8000/

# 预期: 307 Temporary Redirect

# 测试 Web UI
curl http://localhost:8000/static/index.html | head -20

# 预期: 看到 HTML 内容
```

---

## 📍 步骤 6: 初始化数据库表

应用启动时会自动执行，验证一下：

```bash
# 检查数据库是否已创建
ls -la media.db

# 预期: -rw-r--r-- ... media.db (文件存在)
```

---

## 📍 步骤 7: 扫描媒体文件

```bash
# 触发媒体扫描
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"root_path": "/home/yanjun/workspace/project/video,/home/yanjun/workspace/project/img"}'

# 或使用 Web UI 上的"扫描"按钮
```

**预期**: 
- 看到 JSON 响应，包含找到的文件数量
- `app.log` 中出现 "找到 X 个媒体文件"

---

## 📍 步骤 8: 验证新架构

### 检查 Album 相册表

```bash
sqlite3 media.db "SELECT COUNT(*) as albums FROM album;"

# 预期: 显示相册数量（应该 > 0）
```

### 检查 Media 表

```bash
sqlite3 media.db "SELECT COUNT(*) as medias FROM media;"

# 预期: 显示媒体文件数量（应该 > 0）
```

### 查看表结构

```bash
# 显示 Album 表结构
sqlite3 media.db ".schema album"

# 预期输出示例:
# CREATE TABLE album (
#   id INTEGER PRIMARY KEY,
#   name VARCHAR(255) NOT NULL,
#   path VARCHAR(512) NOT NULL UNIQUE,
#   cover_image_path VARCHAR(512),
#   created_at DATETIME NOT NULL,
#   ...
# );
```

---

## 📍 步骤 9: 测试 API 端点

### 获取所有相册

```bash
curl http://localhost:8000/albums

# 预期: 返回相册列表的 JSON
```

### 获取相册详情

```bash
curl http://localhost:8000/albums/1

# 预期: 返回相册信息及其中的媒体文件列表
```

### 获取媒体列表

```bash
curl "http://localhost:8000/media?limit=10"

# 预期: 返回媒体文件列表
```

---

## 📍 步骤 10: 打开 Web UI

在浏览器中访问：

```
http://192.168.31.211:8000
```

或使用相同网络中的电脑：

```
http://192.168.31.211:8000
```

**预期**:
- ✅ 看到 Web UI 页面
- ✅ 看到相册列表
- ✅ 看到媒体文件的缩略图
- ✅ 点击视频能进行播放

---

## ⚠️ 故障排除

### 问题 1: 应用未启动

```bash
# 检查日志
cat app.log

# 查看详细错误
python main.py
```

### 问题 2: 数据库错误

```bash
# 清理 __pycache__
find . -type d -name __pycache__ -exec rm -r {} +

# 重新启动
pkill -f "python main"
sleep 2
python main.py
```

### 问题 3: 端口被占用

```bash
# 检查 8000 端口
lsof -i :8000

# 如果被占用，杀死占用进程
kill -9 <PID>
```

### 问题 4: 无法访问 Web UI

```bash
# 检查暴露的端口
netstat -tulpn | grep 8000

# 检查防火墙
sudo ufw status

# 如果防火墙阻止，允许 8000 端口
sudo ufw allow 8000
```

---

## ✅ 成功检查清单

在完成所有步骤后，检查以下项：

- [ ] 应用进程运行中
- [ ] 可以访问 http://localhost:8000（重定向到 /static/index.html）
- [ ] 数据库文件 media.db 存在
- [ ] Album 表中有数据 (`SELECT COUNT(*) FROM album`)
- [ ] Media 表中有数据 (`SELECT COUNT(*) FROM media`)
- [ ] 可以调用 `/albums` API
- [ ] 可以调用 `/media` API
- [ ] Web UI 显示相册和媒体
- [ ] 视频能够播放
- [ ] 缩略图能够加载

---

## 📚 相关文档

- `REFACTOR_COMPLETION.md` - 重构完成报告
- `SCHEMA_REFACTOR.md` - 架构设计详情
- `db_migrate.py` - 数据库迁移工具

---

## 💡 后续步骤

1. **调整应用代码**
   - 更新 `routers/albums.py` 适配新架构
   - 更新 `services/scanner.py` 创建 Album 记录
   - 更新 `crud.py` 操作逻辑

2. **前端优化**
   - 显示相册分类
   - 相册缩略图展示
   - 相册管理功能

3. **数据迁移**（如果需要保留旧数据）
   - 使用 `db_migrate.py` 迁移历史数据

---

**⏰ 开始启动！**

```bash
pkill -f "python main"; sleep 1; rm -f media.db; cd /home/yanjun/workspace/project && python main.py
```

有任何问题？检查 `app.log` 或查看文档！

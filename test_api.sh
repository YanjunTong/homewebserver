#!/bin/bash
"""
API 测试脚本
"""

BASE_URL="http://localhost:8000"

echo "========== HomeMedia Hub API 测试 =========="
echo ""

# 1. 测试根路由
echo "1️⃣  测试根路由 (GET /)"
echo "请求: curl $BASE_URL/"
curl -s "$BASE_URL/" | python -m json.tool
echo ""
echo ""

# 2. 测试健康检查
echo "2️⃣  健康检查 (GET /health)"
echo "请求: curl $BASE_URL/health"
curl -s "$BASE_URL/health" | python -m json.tool
echo ""
echo ""

# 3. 获取媒体总数
echo "3️⃣  获取媒体总数 (GET /media/count)"
echo "请求: curl $BASE_URL/media/count"
curl -s "$BASE_URL/media/count" | python -m json.tool
echo ""
echo ""

# 4. 获取媒体列表
echo "4️⃣  获取媒体列表 (GET /media?skip=0&limit=5)"
echo "请求: curl '$BASE_URL/media?skip=0&limit=5'"
curl -s "$BASE_URL/media?skip=0&limit=5" | python -m json.tool
echo ""
echo ""

# 5. 扫描图片文件夹
echo "5️⃣  扫描图片文件夹 (POST /scan/images)"
echo "请求: curl -X POST $BASE_URL/scan/images"
curl -s -X POST "$BASE_URL/scan/images" | python -m json.tool
echo ""
echo ""

# 6. 扫描视频文件夹
echo "6️⃣  扫描视频文件夹 (POST /scan/videos)"
echo "请求: curl -X POST $BASE_URL/scan/videos"
curl -s -X POST "$BASE_URL/scan/videos" | python -m json.tool
echo ""
echo ""

echo "========== 测试完成 =========="

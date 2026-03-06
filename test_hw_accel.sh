#!/bin/bash

# 测试 Intel VA-API 硬件加速是否可用

echo "🔍 检测硬件加速环境..."
echo

# 1. 检查 /dev/dri/renderD128 是否存在
echo "1️⃣ 检查 VA-API 设备..."
if [ -e /dev/dri/renderD128 ]; then
    echo "✅ /dev/dri/renderD128 存在 (Intel GPU 渲染设备)"
    ls -lh /dev/dri/renderD128
else
    echo "⚠️ /dev/dri/renderD128 不存在，硬件加速可能不可用"
fi
echo

# 2. 检查 ffmpeg 是否支持 vaapi
echo "2️⃣ 检查 ffmpeg 的 VA-API 支持..."
if ffmpeg -hwaccel ? 2>&1 | grep -q vaapi; then
    echo "✅ ffmpeg 支持 VA-API"
    ffmpeg -hwaccel ? 2>&1 | grep vaapi
else
    echo "⚠️ ffmpeg 可能不支持 VA-API 或未正确安装"
fi
echo

# 3. 检查 ffmpeg-python 库
echo "3️⃣ 检查 Python ffmpeg 库..."
python3 << 'EOF'
try:
    import ffmpeg
    print("✅ ffmpeg-python 库已安装")
except ImportError:
    print("⚠️ ffmpeg-python 库未安装")
EOF
echo

# 4. 测试硬件加速效果
echo "4️⃣ 测试硬件加速性能..."
TEST_VIDEO="video/Screenrecorder-2025-10-21-11-48-34-544.mp4"

if [ -f "$TEST_VIDEO" ]; then
    echo "📹 使用测试视频: $TEST_VIDEO"
    echo
    
    # 不使用硬件加速
    echo "⏱️ 测试 1: 软件解码 (无加速)"
    START_TIME=$(date +%s%N)
    ffmpeg -i "$TEST_VIDEO" -vframes 1 -vf "scale=-1:300" -y /tmp/thumb_software.webp -hide_banner -loglevel error 2>/dev/null
    END_TIME=$(date +%s%N)
    SOFT_TIME=$(( (END_TIME - START_TIME) / 1000000 ))
    echo "✓ 耗时: ${SOFT_TIME}ms"
    echo
    
    # 使用硬件加速
    echo "⏱️ 测试 2: 硬件加速 (VA-API)"
    START_TIME=$(date +%s%N)
    ffmpeg -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -ss 5 -i "$TEST_VIDEO" -vframes 1 -vf "scale=-1:300" -y /tmp/thumb_hwaccel.webp -hide_banner -loglevel error 2>/dev/null
    END_TIME=$(date +%s%N)
    HW_TIME=$(( (END_TIME - START_TIME) / 1000000 ))
    echo "✓ 耗时: ${HW_TIME}ms"
    echo
    
    # 计算加速比
    if [ "$SOFT_TIME" -gt 0 ]; then
        SPEEDUP=$(( SOFT_TIME / HW_TIME ))
        echo "📊 加速比: ${SPEEDUP}x"
        if [ "$SPEEDUP" -gt 1 ]; then
            echo "🚀 硬件加速有效！"
        else
            echo "⚠️ 硬件加速可能未生效，但已正确配置"
        fi
    fi
    
    # 清理测试文件
    rm -f /tmp/thumb_software.webp /tmp/thumb_hwaccel.webp
else
    echo "❌ 测试视频不存在：$TEST_VIDEO"
fi
echo

echo "✅ 检测完成！"

import os
import shutil

# --- 配置区域 ---
# 你要整理的源文件夹路径
SOURCE_DIR ='/home/yanjun/workspace/project/web/src'
# 图片存放的目标路径
IMAGE_DEST = '/home/yanjun/workspace/project/img'
# 视频存放的目标路径
VIDEO_DEST = '/home/yanjun/workspace/project/video'

# 定义后缀名（可以根据需要增减）
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv'}

def move_files():
    # 如果目标文件夹不存在，则创建
    for folder in [IMAGE_DEST, VIDEO_DEST]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"创建文件夹: {folder}")

    count_img = 0
    count_vid = 0

    # 遍历文件夹（包括子文件夹）
    for root, dirs, files in os.walk(SOURCE_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()

            # 判断类型
            dest_dir = None
            if ext in IMAGE_EXTS:
                dest_dir = IMAGE_DEST
                count_img += 1
            elif ext in VIDEO_EXTS:
                dest_dir = VIDEO_DEST
                count_vid += 1

            # 执行移动操作
            if dest_dir:
                # 处理重名冲突
                base_name = os.path.basename(file)
                dest_path = os.path.join(dest_dir, base_name)
                
                # 如果文件已存在，则重命名（例如 photo.jpg -> photo_1.jpg）
                counter = 1
                name_part, ext_part = os.path.splitext(base_name)
                while os.path.exists(dest_path):
                    dest_path = os.path.join(dest_dir, f"{name_part}_{counter}{ext_part}")
                    counter += 1
                
                shutil.move(file_path, dest_path)
                print(f"已移动: {base_name} -> {os.path.basename(dest_path)}")

    print("-" * 30)
    print(f"整理完成！共移动图片 {count_img} 张，视频 {count_vid} 个。")

if __name__ == "__main__":
    move_files()
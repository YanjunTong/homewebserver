"""应用配置管理"""
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置"""
    # 应用信息
    app_name: str = "HomeMedia Hub"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # 媒体文件夹配置
    content_folder: str = "/home/yanjun/media/test_content"
    
    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./media.db"
    
    class Config:
        # 读取 .env 文件
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# 全局配置实例
settings = Settings()

# 确保配置文件夹存在
def ensure_folders_exist():
    """确保配置的文件夹存在"""
    folders = [
        settings.content_folder,
        Path(__file__).parent / "static",
    ]
    
    for folder in folders:
        path = Path(folder)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"✓ 创建文件夹: {folder}")
        else:
            print(f"✓ 文件夹已存在: {folder}")

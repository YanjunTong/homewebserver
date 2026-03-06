#!/usr/bin/env python3
"""
数据库架构迁移指南

本脚本用于从旧的" Many-to-Many Album-Media" 架构迁移到新的"One Folder = One Album"架构。

变更概述：
1. Album 模型：
   - 新增 path 字段（唯一的文件夹绝对路径）
   - 新增 cover_image_path 字段（第一张图片路径）
   - 删除 description 字段（简化数据结构）

2. Media 模型：
   - 新增 album_id 字段（外键，必须）
   - 改为一对多关系（每个 Media 只属于一个 Album）

3. 关系变更：
   - 删除 album_media_association 多对多关联表
   - 删除 AlbumMediaLink 模型
   - 实现一对多关系清晰

推荐步骤：
1. 备份当前数据库：sqlite3 media.db ".backup media.db.backup"
2. 删除旧数据库或使用新的数据库名称
3. 运行应用，自动创建新架构的表
4. 如果需要迁移数据：
   - 编写数据迁移脚本
   - 为每个旧的 Media 创建对应的 Album
   - 基于物理路径将 Media 映射到 Album
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_engine, AsyncSessionLocal
from models import Album, Media

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def migrate_schema():
    """
    迁移架构（从多对多改为一对多）
    
    警告：此操作将删除所有现有的 Album 和 Media 数据！
    如果需要保留数据，请先备份！
    """
    print("=" * 60)
    print("📋 数据库架构迁移")
    print("=" * 60)
    print()
    print("⚠️  警告：此操作将重新创建数据库表结构")
    print("   所有现有数据将丢失！")
    print()
    print("确认继续？(y/n): ", end="")
    
    if input().lower() != "y":
        print("❌ 迁移已取消")
        return
    
    try:
        # 删除所有现有表
        print()
        print("🗑️  删除旧表...", end=" ", flush=True)
        async with async_engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute(
                "DROP TABLE IF EXISTS album_media_link"
            ))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(
                "DROP TABLE IF EXISTS album_media_link_model"
            ))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(
                "DROP TABLE IF EXISTS media"
            ))
            await conn.run_sync(lambda sync_conn: sync_conn.execute(
                "DROP TABLE IF EXISTS album"
            ))
        print("✅ 完成")
        
        # 创建新表
        print("📝 创建新表...", end=" ", flush=True)
        async with async_engine.begin() as conn:
            from models import Base
            await conn.run_sync(Base.metadata.create_all)
        print("✅ 完成")
        
        print()
        print("=" * 60)
        print("✅ 架构迁移成功！")
        print("=" * 60)
        print()
        print("新架构特性：")
        print("  • Album 表：")
        print("    - id (PK)")
        print("    - name (文件夹名称，唯一索引)")
        print("    - path (文件夹绝对路径，唯一约束)")
        print("    - cover_image_path (首张图片路径，可选)")
        print("    - created_at")
        print()
        print("  • Media 表：")
        print("    - id (PK)")
        print("    - album_id (FK → album.id，必须)")
        print("    - filename")
        print("    - file_path (唯一)")
        print("    - media_type (image/video)")
        print("    - size")
        print("    - width, height (可选)")
        print("    - duration (可选)")
        print("    - created_at")
        print("    - is_favorite")
        print("    - thumbnail_path (可选)")
        print()
        print("下一步：")
        print("  1. 重启应用")
        print("  2. 重新扫描媒体文件夹")
        print("  3. 系统会自动为每个扫描的文件夹创建 Album")
        print()
        
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        print(f"❌ 失败: {e}")
        raise


async def show_schema_info():
    """显示数据库架构信息"""
    print()
    print("=" * 60)
    print("📊 数据库架构 - 一个文件夹 = 一个相册")
    print("=" * 60)
    print()
    
    try:
        async with AsyncSessionLocal() as session:
            # 查询 Album 数量
            album_count = await session.execute(select(lambda: None).select_from(Album))
            albums = await session.execute(select(Album))
            album_list = albums.scalars().all()
            
            # 查询 Media 数量
            from sqlalchemy import func
            media_count_stmt = select(func.count(Media.id))
            media_count_result = await session.execute(media_count_stmt)
            media_count = media_count_result.scalar() or 0
            
            print(f"相册（文件夹）数量: {len(album_list)}")
            print(f"媒体文件数量: {media_count}")
            print()
            
            if album_list:
                print("相册列表：")
                for album in album_list[:10]:  # 显示前10个
                    media_in_album = len(album.media_items) if hasattr(album, 'media_items') else 0
                    print(f"  • {album.name} ({album.path})")
                    print(f"    - 媒体数: {media_in_album}")
                    if album.cover_image_path:
                        print(f"    - 封面: {album.cover_image_path}")
                    print()
                
                if len(album_list) > 10:
                    print(f"  ... 以及 {len(album_list) - 10} 个其他相册")
            
            print()
            
    except Exception as e:
        logger.error(f"查询架构信息失败: {e}")
        print(f"信息：数据库可能为空或不存在")


async def main():
    """主入口"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        # 执行迁移
        await migrate_schema()
    else:
        # 显示架构信息
        await show_schema_info()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏸️  已中止")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

#!/usr/bin/env python3
"""
测试脚本: 目录级相册扫描演示

演示新的扫描逻辑:
- Step 1: 扫描文件夹创建相册
- Step 2: 扫描文件创建媒体记录
- Cleanup: 删除不存在的相册和文件
"""

import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import Base, Album, Media
from services.scanner import scan_directory_based, scan_files_in_album
from config import settings


async def demo_scan():
    """演示扫描过程"""
    
    # 1. 建立数据库连接
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("=" * 60)
    print("🎯 目录级相册扫描 - 演示")
    print("=" * 60)
    
    async with async_session() as db:
        # 执行扫描
        root_path = settings.image_folder
        print(f"\n📂 扫描根目录: {root_path}")
        print("=" * 60)
        
        result = await scan_directory_based(db, root_path)
        
        # 打印结果
        print(f"\n📊 扫描结果:")
        print(f"  相册 - 创建: {result['albums_created']}, 删除: {result['albums_deleted']}")
        print(f"  文件 - 添加: {result['files_added']}, 跳过: {result['files_skipped']}, 删除: {result['files_deleted']}, 失败: {result['files_failed']}")
        
        if result['errors']:
            print(f"\n⚠️  错误:")
            for error in result['errors']:
                print(f"  - {error}")
        
        # 查询数据库统计
        from sqlalchemy import select, func
        
        albums_count = await db.execute(select(func.count(Album.id)))
        media_count = await db.execute(select(func.count(Media.id)))
        
        print(f"\n📈 数据库统计:")
        print(f"  相册总数: {albums_count.scalar()}")
        print(f"  媒体总数: {media_count.scalar()}")
        
        # 列出前几个相册
        from sqlalchemy import select
        stmt = select(Album).limit(5)
        albums_result = await db.execute(stmt)
        albums = albums_result.scalars().all()
        
        if albums:
            print(f"\n📚 相册列表 (前 5 个):")
            for album in albums:
                print(f"  [{album.id}] {album.name}")
                print(f"      路径: {album.path}")
                if album.cover_image_path:
                    print(f"      封面: {Path(album.cover_image_path).name}")
                
                # 统计该相册的媒体
                media_count_stmt = select(func.count(Media.id)).where(Media.album_id == album.id)
                media_result = await db.execute(media_count_stmt)
                count = media_result.scalar()
                print(f"      文件数: {count}")
    
    await engine.dispose()
    print("\n✅ 演示完成！")


if __name__ == "__main__":
    asyncio.run(demo_scan())

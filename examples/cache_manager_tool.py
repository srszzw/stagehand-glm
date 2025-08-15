"""
Stagehand 缓存管理工具
提供缓存查看、清理、导入导出等功能
"""

import argparse
import json
import os
from datetime import datetime

from stagehand.cache import StagehandCache


def display_cache_stats(cache_manager: StagehandCache):
    """显示缓存统计信息"""
    stats = cache_manager.get_cache_stats()

    print("📊 缓存统计信息:")
    print("=" * 50)
    print(f"总缓存数量: {stats['total_caches']}")
    print(f"总命中次数: {stats['total_hits']}")
    print(f"内存缓存大小: {stats['memory_cache_size']}")
    print(f"缓存文件: {stats['cache_file']}")
    print(f"缓存版本: {stats['version']}")
    print("=" * 50)


def display_cache_details(cache_manager: StagehandCache):
    """显示缓存详细信息"""
    caches = cache_manager.cache_data.get("caches", {})

    if not caches:
        print("📭 暂无缓存记录")
        return

    print(f"📋 缓存详细信息 (共 {len(caches)} 条):")
    print("=" * 80)

    for i, (cache_key, cache_item) in enumerate(caches.items(), 1):
        print(f"\n[{i}] 缓存记录:")
        print(f"  🔑 Key: {cache_key[:16]}...")
        print(f"  📝 指令: {cache_item.get('instruction', 'N/A')[:60]}...")
        print(f"  🌐 页面: {cache_item.get('page_url', 'N/A')}")
        print(f"  🎯 XPath: {cache_item.get('result', {}).get('selector', 'N/A')}")
        print(f"  📅 创建时间: {cache_item.get('created_at', 'N/A')}")
        print(f"  🔥 命中次数: {cache_item.get('hit_count', 0)}")
        print(f"  ⏰ 最后使用: {cache_item.get('last_used', 'N/A')}")


def clear_cache(cache_manager: StagehandCache, expired_only: bool = False):
    """清理缓存"""
    if expired_only:
        cleared = cache_manager.clear_cache(expired_only=True, ttl=3600)
        print(f"🧹 已清理 {cleared} 条过期缓存")
    else:
        cleared = cache_manager.clear_cache(expired_only=False)
        print(f"🧹 已清理所有缓存 ({cleared} 条)")


def export_cache(cache_manager: StagehandCache, export_file: str):
    """导出缓存到文件"""
    try:
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(cache_manager.cache_data, f, ensure_ascii=False, indent=2)
        print(f"📤 缓存已导出到: {export_file}")
    except Exception as e:
        print(f"❌ 导出失败: {e}")


def import_cache(cache_manager: StagehandCache, import_file: str):
    """从文件导入缓存"""
    try:
        if not os.path.exists(import_file):
            print(f"❌ 文件不存在: {import_file}")
            return

        with open(import_file, "r", encoding="utf-8") as f:
            imported_data = json.load(f)

        # 合并缓存数据
        current_caches = cache_manager.cache_data.get("caches", {})
        imported_caches = imported_data.get("caches", {})

        merged_count = 0
        for key, value in imported_caches.items():
            if key not in current_caches:
                current_caches[key] = value
                merged_count += 1

        cache_manager._save_cache()
        print(f"📥 已导入 {merged_count} 条新缓存记录")

    except Exception as e:
        print(f"❌ 导入失败: {e}")


def search_cache(cache_manager: StagehandCache, keyword: str):
    """搜索缓存"""
    caches = cache_manager.cache_data.get("caches", {})
    matched_caches = []

    for cache_key, cache_item in caches.items():
        instruction = cache_item.get("instruction", "").lower()
        page_url = cache_item.get("page_url", "").lower()
        description = cache_item.get("result", {}).get("description", "").lower()

        if (
            keyword.lower() in instruction
            or keyword.lower() in page_url
            or keyword.lower() in description
        ):
            matched_caches.append((cache_key, cache_item))

    if not matched_caches:
        print(f"🔍 未找到包含 '{keyword}' 的缓存记录")
        return

    print(f"🔍 找到 {len(matched_caches)} 条匹配记录:")
    print("=" * 60)

    for i, (cache_key, cache_item) in enumerate(matched_caches, 1):
        print(f"\n[{i}] 匹配记录:")
        print(f"  📝 指令: {cache_item.get('instruction', 'N/A')}")
        print(f"  🌐 页面: {cache_item.get('page_url', 'N/A')}")
        print(f"  🎯 描述: {cache_item.get('result', {}).get('description', 'N/A')}")
        print(f"  🔥 命中次数: {cache_item.get('hit_count', 0)}")


def main():
    parser = argparse.ArgumentParser(description="Stagehand 缓存管理工具")
    parser.add_argument(
        "--cache-file", default="stagehand_cache.json", help="缓存文件路径"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 统计信息
    subparsers.add_parser("stats", help="显示缓存统计信息")

    # 详细信息
    subparsers.add_parser("list", help="显示缓存详细信息")

    # 清理缓存
    clear_parser = subparsers.add_parser("clear", help="清理缓存")
    clear_parser.add_argument(
        "--expired-only", action="store_true", help="只清理过期缓存"
    )

    # 导出缓存
    export_parser = subparsers.add_parser("export", help="导出缓存")
    export_parser.add_argument("file", help="导出文件路径")

    # 导入缓存
    import_parser = subparsers.add_parser("import", help="导入缓存")
    import_parser.add_argument("file", help="导入文件路径")

    # 搜索缓存
    search_parser = subparsers.add_parser("search", help="搜索缓存")
    search_parser.add_argument("keyword", help="搜索关键词")

    args = parser.parse_args()

    # 创建缓存管理器
    cache_manager = StagehandCache(cache_file=args.cache_file)

    if args.command == "stats":
        display_cache_stats(cache_manager)
    elif args.command == "list":
        display_cache_details(cache_manager)
    elif args.command == "clear":
        clear_cache(cache_manager, args.expired_only)
    elif args.command == "export":
        export_cache(cache_manager, args.file)
    elif args.command == "import":
        import_cache(cache_manager, args.file)
    elif args.command == "search":
        search_cache(cache_manager, args.keyword)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

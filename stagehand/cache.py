"""
Stagehand 缓存管理器
提供智能缓存功能，减少LLM调用，提升性能
"""

import json
import hashlib
import time
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio

from .schemas import ObserveResult
from .logging import StagehandLogger


class StagehandCache:
    """Stagehand 缓存管理器"""

    def __init__(
        self,
        cache_file: str = "stagehand_cache.json",
        logger: Optional[StagehandLogger] = None,
    ):
        """
        初始化缓存管理器

        Args:
            cache_file: 缓存文件路径
            logger: 日志记录器
        """
        self.cache_file = cache_file
        self.logger = logger
        self.cache_data = self._load_cache()
        self._memory_cache = {}  # 内存缓存，提升性能

    def _load_cache(self) -> Dict[str, Any]:
        """加载缓存文件"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if self.logger:
                        self.logger.info(
                            f"✅ 加载缓存文件成功，包含 {len(data.get('caches', {}))} 条记录"
                        )
                    return data
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ 加载缓存文件失败: {e}")

        # 返回默认缓存结构
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "caches": {},
        }

    def _save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            self.cache_data["last_updated"] = datetime.now().isoformat()
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
            if self.logger:
                self.logger.debug("💾 缓存文件保存成功")
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ 保存缓存文件失败: {e}")

    def _generate_cache_key(
        self, instruction: str, page_url: str, page_title: str = None
    ) -> str:
        """
        生成缓存key

        Args:
            instruction: 用户指令
            page_url: 页面URL
            page_title: 页面标题（可选）

        Returns:
            缓存key的哈希值
        """
        # 创建复合key
        key_components = {
            "instruction": instruction.strip().lower(),
            "page_url": page_url,
            "page_title": page_title or "",
        }

        # 生成哈希
        key_string = json.dumps(key_components, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key_string.encode("utf-8")).hexdigest()

    def get_cached_result(
        self, instruction: str, page_url: str, page_title: str = None, ttl: int = 3600
    ) -> Optional[ObserveResult]:
        """
        获取缓存的观察结果

        Args:
            instruction: 用户指令
            page_url: 页面URL
            page_title: 页面标题
            ttl: 缓存生存时间（秒）

        Returns:
            缓存的ObserveResult或None
        """
        cache_key = self._generate_cache_key(instruction, page_url, page_title)

        # 先检查内存缓存
        if cache_key in self._memory_cache:
            cached_item = self._memory_cache[cache_key]
            if self._is_cache_valid(cached_item, ttl):
                if self.logger:
                    self.logger.info(f"🚀 内存缓存命中: {instruction[:50]}...")
                self._update_cache_stats(cache_key, hit=True)
                return self._create_observe_result_from_cache(cached_item["result"])

        # 检查文件缓存
        caches = self.cache_data.get("caches", {})
        if cache_key in caches:
            cached_item = caches[cache_key]
            if self._is_cache_valid(cached_item, ttl):
                if self.logger:
                    self.logger.info(f"📁 文件缓存命中: {instruction[:50]}...")

                # 加载到内存缓存
                self._memory_cache[cache_key] = cached_item
                self._update_cache_stats(cache_key, hit=True)
                return self._create_observe_result_from_cache(cached_item["result"])
            else:
                # 缓存过期，删除
                if self.logger:
                    self.logger.info(f"⏰ 缓存过期，删除: {instruction[:50]}...")
                del caches[cache_key]
                self._save_cache()

        if self.logger:
            self.logger.debug(f"❌ 缓存未命中: {instruction[:50]}...")
        return None

    def set_cache(
        self,
        instruction: str,
        page_url: str,
        result: ObserveResult,
        page_title: str = None,
    ) -> None:
        """
        设置缓存

        Args:
            instruction: 用户指令
            page_url: 页面URL
            result: ObserveResult结果
            page_title: 页面标题
        """
        cache_key = self._generate_cache_key(instruction, page_url, page_title)

        cache_item = {
            "instruction": instruction,
            "page_url": page_url,
            "page_title": page_title or "",
            "result": {
                "selector": result.selector,
                "description": result.description,
                "method": result.method,
                "arguments": result.arguments,
                "backend_node_id": result.backend_node_id,
            },
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
            "hit_count": 0,
        }

        # 保存到内存和文件缓存
        self._memory_cache[cache_key] = cache_item
        self.cache_data["caches"][cache_key] = cache_item
        self._save_cache()

        if self.logger:
            self.logger.info(f"💾 缓存已保存: {instruction[:50]}...")

    def _is_cache_valid(self, cached_item: Dict[str, Any], ttl: int) -> bool:
        """检查缓存是否有效"""
        try:
            created_at = datetime.fromisoformat(cached_item["created_at"])
            return datetime.now() - created_at < timedelta(seconds=ttl)
        except:
            return False

    def _create_observe_result_from_cache(
        self, cached_result: Dict[str, Any]
    ) -> ObserveResult:
        """从缓存数据创建ObserveResult对象"""
        return ObserveResult(
            selector=cached_result["selector"],
            description=cached_result["description"],
            method=cached_result.get("method"),
            arguments=cached_result.get("arguments"),
            backend_node_id=cached_result.get("backend_node_id"),
        )

    def _update_cache_stats(self, cache_key: str, hit: bool = True) -> None:
        """更新缓存统计信息"""
        # 更新内存缓存统计
        if cache_key in self._memory_cache:
            if hit:
                self._memory_cache[cache_key]["hit_count"] += 1
                self._memory_cache[cache_key]["last_used"] = datetime.now().isoformat()

        # 更新文件缓存统计
        caches = self.cache_data.get("caches", {})
        if cache_key in caches:
            if hit:
                caches[cache_key]["hit_count"] += 1
                caches[cache_key]["last_used"] = datetime.now().isoformat()

    async def validate_cached_xpath(self, page, xpath: str) -> bool:
        """
        验证缓存的xpath是否仍然有效

        Args:
            page: StagehandPage实例
            xpath: 要验证的xpath

        Returns:
            xpath是否有效
        """
        try:
            # 移除xpath=前缀（如果存在）
            clean_xpath = xpath.replace("xpath=", "")

            # 尝试定位元素
            locator = page._page.locator(f"xpath={clean_xpath}").first

            # 检查元素是否存在
            count = await locator.count()
            return count > 0

        except Exception as e:
            if self.logger:
                self.logger.debug(f"XPath验证失败: {xpath}, 错误: {e}")
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        caches = self.cache_data.get("caches", {})
        total_caches = len(caches)
        total_hits = sum(cache.get("hit_count", 0) for cache in caches.values())

        # 计算内存缓存大小
        memory_cache_size = len(self._memory_cache)

        return {
            "total_caches": total_caches,
            "total_hits": total_hits,
            "memory_cache_size": memory_cache_size,
            "cache_file": self.cache_file,
            "version": self.cache_data.get("version", "unknown"),
        }

    def clear_cache(self, expired_only: bool = False, ttl: int = 3600) -> int:
        """
        清理缓存

        Args:
            expired_only: 是否只清理过期的缓存
            ttl: 过期时间（秒）

        Returns:
            清理的缓存数量
        """
        cleared_count = 0
        caches = self.cache_data.get("caches", {})

        if expired_only:
            # 只清理过期缓存
            expired_keys = []
            for key, cached_item in caches.items():
                if not self._is_cache_valid(cached_item, ttl):
                    expired_keys.append(key)

            for key in expired_keys:
                del caches[key]
                if key in self._memory_cache:
                    del self._memory_cache[key]
                cleared_count += 1
        else:
            # 清理所有缓存
            cleared_count = len(caches)
            caches.clear()
            self._memory_cache.clear()

        if cleared_count > 0:
            self._save_cache()
            if self.logger:
                self.logger.info(f"🧹 已清理 {cleared_count} 条缓存记录")

        return cleared_count

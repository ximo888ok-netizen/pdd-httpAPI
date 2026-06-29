# -*- coding: utf-8 -*-
"""
拼多多 API 聚合 SDK 客户端
=========================
统一入口，聚合 6 大业务模块 + 扫码登录。
支持多店铺：通过 mall_id 区分，cookies 从 cookies.json 持久化加载。

使用示例:
    from client import PDDClient

    # 方式1：指定已登录店铺
    client = PDDClient(mall_id="256393917")

    # 方式2：扫码登录后自动绑定
    client = PDDClient()
    result = client.login(timeout=120)
    # result = {"mall_id": ..., "username": ..., "cookies": ...}

    # 调用业务接口
    user = client.auth_shop.get_user_info()
    client.customer_service.send_text(to_uid="xxx", content="你好")
"""
import logging
from typing import Optional, Dict, Any, Callable

from auth import PDDAuth
from base_request import BaseRequest
from apis import (
    AuthShopAPI,
    CustomerServiceAPI,
    DataCenterAPI,
    ReviewAPI,
    ActivityEnrollAPI,
    ProductAPI,
)

logger = logging.getLogger("pdd_client")


class PDDClient:
    """拼多多 API 聚合客户端（多店铺支持）"""

    def __init__(self, mall_id: Optional[str] = None, cookies: Optional[Dict] = None,
                 auto_login: bool = False, max_retries: int = 3,
                 min_request_interval: float = 0.5):
        """
        Args:
            mall_id: 店铺 ID。指定时从 cookies.json 加载对应 cookies。
            cookies: 直接传入 cookies 字典（优先级高于 mall_id 加载）。
            auto_login: 会话过期时是否自动重新登录（需先登录过，cookies 中有 mall_id）。
            max_retries: 请求最大重试次数
            min_request_interval: 全局最小请求间隔（秒）
        """
        self.auth = PDDAuth()
        self.mall_id = mall_id
        self.auto_login = auto_login
        self.max_retries = max_retries
        self.min_request_interval = min_request_interval

        # 加载 cookies
        if cookies:
            self.cookies = cookies
        elif mall_id:
            loaded = self.auth.load_cookies(mall_id)
            if loaded:
                self.cookies = loaded
                logger.info("已从 cookies.json 加载店铺 %s 的 cookies", mall_id)
            else:
                self.cookies = {}
                logger.warning("cookies.json 中未找到店铺 %s，请先登录", mall_id)
        else:
            self.cookies = {}

        # 重新登录回调
        self._relogin_cb = None
        if auto_login and mall_id:
            self._relogin_cb = self.auth.make_relogin_callback()

        # 懒加载各 API 实例
        self._auth_shop = None
        self._customer_service = None
        self._data_center = None
        self._review = None
        self._activity = None
        self._product = None

    # ── 登录 ──────────────────────────────────────────────────────────

    def login(self, timeout: int = 120,
              on_status: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """扫码登录，成功后自动保存 cookies 并绑定 mall_id

        Args:
            timeout: 等待扫码超时秒数
            on_status: 状态回调 callback(status: int, info: dict)

        Returns:
            {"mall_id": ..., "user_id": ..., "username": ..., "cookies": ...} 或 None
        """
        result = self.auth.login(timeout=timeout, on_status=on_status)
        if not result:
            return None
        mall_id = str(result["mall_id"])
        self.auth.save_cookies(mall_id, result["cookies"],
                               result.get("user_id"), result.get("username", ""))
        self.mall_id = mall_id
        self.cookies = result["cookies"]
        self._reset_api_instances()
        logger.info("登录成功并已绑定 mall_id=%s", mall_id)
        return {"mall_id": mall_id, "user_id": result.get("user_id"),
                "username": result.get("username", ""), "cookies": result["cookies"]}

    def _reset_api_instances(self):
        self._auth_shop = None
        self._customer_service = None
        self._data_center = None
        self._review = None
        self._activity = None
        self._product = None

    def _make_kwargs(self) -> Dict[str, Any]:
        kw = {
            "cookies": self.cookies,
            "mall_id": self.mall_id,
            "max_retries": self.max_retries,
            "min_request_interval": self.min_request_interval,
        }
        if self.auto_login and self._relogin_cb:
            kw["auto_relogin"] = True
            kw["relogin_callback"] = self._relogin_cb
        return kw

    def update_cookies(self, new_cookies: Dict) -> None:
        """更新 cookies 并重置 API 实例"""
        self.cookies = new_cookies
        self._reset_api_instances()
        if self.mall_id:
            self.auth.save_cookies(self.mall_id, new_cookies)

    # ── 店铺管理 ──────────────────────────────────────────────────────

    def list_malls(self) -> list:
        """列出所有已登录店铺"""
        return self.auth.list_malls()

    def logout(self) -> bool:
        """登出当前店铺"""
        if self.mall_id:
            return self.auth.logout(self.mall_id)
        return False

    def switch_mall(self, mall_id: str) -> bool:
        """切换到另一个已登录店铺"""
        loaded = self.auth.load_cookies(mall_id)
        if loaded:
            self.mall_id = mall_id
            self.cookies = loaded
            self._reset_api_instances()
            logger.info("已切换到店铺 %s", mall_id)
            return True
        logger.warning("切换失败：cookies.json 中未找到店铺 %s", mall_id)
        return False

    # ── 业务模块（懒加载） ────────────────────────────────────────────

    @property
    def auth_shop(self) -> AuthShopAPI:
        if self._auth_shop is None:
            self._auth_shop = AuthShopAPI(**self._make_kwargs())
        return self._auth_shop

    @property
    def customer_service(self) -> CustomerServiceAPI:
        if self._customer_service is None:
            self._customer_service = CustomerServiceAPI(**self._make_kwargs())
        return self._customer_service

    @property
    def data_center(self) -> DataCenterAPI:
        if self._data_center is None:
            self._data_center = DataCenterAPI(**self._make_kwargs())
        return self._data_center

    @property
    def review(self) -> ReviewAPI:
        if self._review is None:
            self._review = ReviewAPI(**self._make_kwargs())
        return self._review

    @property
    def activity(self) -> ActivityEnrollAPI:
        if self._activity is None:
            self._activity = ActivityEnrollAPI(**self._make_kwargs())
        return self._activity

    @property
    def product(self) -> ProductAPI:
        if self._product is None:
            self._product = ProductAPI(**self._make_kwargs())
        return self._product

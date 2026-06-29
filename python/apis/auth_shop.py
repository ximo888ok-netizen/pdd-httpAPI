# -*- coding: utf-8 -*-
"""认证与店铺信息 API（4 端点，来自 01_auth_and_shop.json）"""
from typing import Optional, Dict, Any
from base_request import BaseRequest

BASE = "https://mms.pinduoduo.com"


class AuthShopAPI(BaseRequest):
    """认证与店铺信息接口"""

    def get_token(self) -> Optional[Dict[str, Any]]:
        """获取聊天 WebSocket token → POST /chats/getToken"""
        url = f"{BASE}/chats/getToken"
        return self.post(url, data="")

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """获取当前登录用户信息 → POST /janus/api/new/userinfo"""
        url = f"{BASE}/janus/api/new/userinfo"
        return self.post(url, data="")

    def get_shop_info(self) -> Optional[Dict[str, Any]]:
        """获取店铺信息（mallId/mallName/mallLogo）→ POST /earth/api/merchant/queryMerchantInfoByMallId"""
        url = f"{BASE}/earth/api/merchant/queryMerchantInfoByMallId"
        return self.post(url, data="")

    def set_csstatus(self, status: int) -> Optional[Dict[str, Any]]:
        """设置客服在线状态 → POST /plateau/chat/set_csstatus

        Args:
            status: 1=上线, 0=离线
        """
        url = f"{BASE}/plateau/chat/set_csstatus"
        return self.post(url, json_data={"status": status})

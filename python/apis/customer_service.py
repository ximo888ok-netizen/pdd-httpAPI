# -*- coding: utf-8 -*-
"""客服消息 API（5 端点，来自 02_customer_service.json）"""
from typing import Optional, Dict, Any
from base_request import BaseRequest

BASE = "https://mms.pinduoduo.com"
CHAT_REFERER = "https://mms.pinduoduo.com/chat-merchant/index.html"


class CustomerServiceAPI(BaseRequest):
    """客服消息接口"""

    def send_text(self, to_uid: str, content: str) -> Optional[Dict[str, Any]]:
        """发送文本消息 → POST /plateau/chat/send_message (type=0)

        Args:
            to_uid: 接收方用户 UID
            content: 文本内容
        """
        url = f"{BASE}/plateau/chat/send_message"
        data = {
            "data": {
                "cmd": "send_message",
                "request_id": self.generate_request_id(),
                "message": {
                    "to": {"role": "user", "uid": to_uid},
                    "from": {"role": "mall_cs"},
                    "content": content,
                    "msg_id": None,
                    "type": 0,
                    "is_aut": 0,
                    "manual_reply": 1,
                },
            },
            "client": "WEB",
        }
        return self.post(url, json_data=data, referer=CHAT_REFERER)

    def send_image(self, to_uid: str, image_url: str) -> Optional[Dict[str, Any]]:
        """发送图片消息 → POST /plateau/chat/send_message (type=1)

        Args:
            to_uid: 接收方用户 UID
            image_url: 图片 URL
        """
        url = f"{BASE}/plateau/chat/send_message"
        data = {
            "data": {
                "cmd": "send_message",
                "request_id": self.generate_request_id(),
                "message": {
                    "to": {"role": "user", "uid": to_uid},
                    "from": {"role": "mall_cs"},
                    "content": image_url,
                    "msg_id": None,
                    "chat_type": "cs",
                    "type": 1,
                    "is_aut": 0,
                    "manual_reply": 1,
                }
            },
            "client": "WEB",
        }
        return self.post(url, json_data=data, referer=CHAT_REFERER)

    def send_goods_card(self, to_uid: str, goods_id: int,
                        biz_type: int = 2) -> Optional[Dict[str, Any]]:
        """发送商品卡片 → POST /plateau/message/send/mallGoodsCard

        Args:
            to_uid: 接收方用户 UID
            goods_id: 商品 ID
            biz_type: 业务类型，默认 2（客服推荐商品）
        """
        url = f"{BASE}/plateau/message/send/mallGoodsCard"
        data = {"uid": to_uid, "goods_id": goods_id, "biz_type": biz_type}
        return self.post(url, json_data=data, referer=CHAT_REFERER)

    def get_assign_cs_list(self) -> Optional[Dict[str, Any]]:
        """获取可分配的客服列表 → POST /latitude/assign/getAssignCsList"""
        url = f"{BASE}/latitude/assign/getAssignCsList"
        return self.post(url, json_data={"wechatCheck": True}, referer=CHAT_REFERER)

    def move_conversation(self, uid: str, cs_uid: str,
                          remark: str = "无原因直接转移") -> Optional[Dict[str, Any]]:
        """转移/转接会话 → POST /plateau/chat/move_conversation

        Args:
            uid: 用户 UID（会话对方）
            cs_uid: 目标客服 UID
            remark: 转接备注
        """
        url = f"{BASE}/plateau/chat/move_conversation"
        data = {
            "data": {
                "cmd": "move_conversation",
                "request_id": self.generate_request_id(),
                "conversation": {
                    "csid": cs_uid,
                    "uid": uid,
                    "need_wx": False,
                    "remark": remark,
                }
            },
            "client": "WEB",
        }
        return self.post(url, json_data=data, referer=CHAT_REFERER)

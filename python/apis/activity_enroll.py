# -*- coding: utf-8 -*-
"""活动报名 API（6 端点，来自 05_activity_enroll.json）"""
import logging
from typing import Optional, Dict, Any, List
from base_request import BaseRequest

BASE = "https://mms.pinduoduo.com"
ACT_REFERER = "https://mms.pinduoduo.com/activity"

logger = logging.getLogger("pdd_activity")


class ActivityEnrollAPI(BaseRequest):
    """活动报名接口"""

    def check_login(self) -> Optional[Dict[str, Any]]:
        """登录状态探针 → POST /janus/api/checkLogin"""
        url = f"{BASE}/janus/api/checkLogin"
        return self.post(url, json_data={}, referer=ACT_REFERER)

    def get_activity_detail(self, activity_id: int) -> Optional[Dict[str, Any]]:
        """查询活动详情 → POST /leekmms/activity/query/detail

        Args:
            activity_id: 活动 ID
        """
        url = f"{BASE}/leekmms/activity/query/detail"
        return self.post(url, json_data={"activity_id": activity_id, "query_source": 1},
                         referer=ACT_REFERER)

    def get_eligible_goods(self, activity_id: int, goods_id: Optional[int] = None,
                           goods_name: str = "", page: int = 1,
                           page_size: int = 10) -> Optional[Dict[str, Any]]:
        """查询可报名商品 → POST /leekmms/activity/query/eligible/goods/listV2"""
        url = f"{BASE}/leekmms/activity/query/eligible/goods/listV2"
        data = {
            "activity_id": activity_id,
            "goods_name": goods_name,
            "page_number": page,
            "eligible": 1,
            "page_size": page_size,
        }
        if goods_id is not None:
            data["goods_id"] = goods_id
        return self.post(url, json_data=data, referer=ACT_REFERER)

    def get_price_rules(self, activity_id: int,
                        goods_id_list: List[int]) -> Optional[Dict[str, Any]]:
        """获取价格规则 → POST /leekmms/activity/query/enroll/rule_v3

        Args:
            activity_id: 活动 ID
            goods_id_list: 商品 ID 列表
        """
        url = f"{BASE}/leekmms/activity/query/enroll/rule_v3"
        return self.post(url,
                         json_data={"activity_id": activity_id, "goods_id_list": goods_id_list},
                         referer=ACT_REFERER)

    def get_suggest_prices(self, activity_id: int,
                           goods_id_list: List[int]) -> Optional[Dict[str, Any]]:
        """获取建议价 → POST /leekmms/activity/query/enroll/rule_suggest_price"""
        url = f"{BASE}/leekmms/activity/query/enroll/rule_suggest_price"
        data = {
            "activity_id": activity_id,
            "goods_id_list": goods_id_list,
            "source_type": "PROMO-HomeModule",
        }
        return self.post(url, json_data=data, referer=ACT_REFERER)

    def do_enroll(self, activity_id: int,
                  goods_volist: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """执行活动报名 → POST /lakemms/enrollV2

        Args:
            activity_id: 活动 ID
            goods_volist: 报名商品列表，每项含 goods_id, enroll_rule_param, sku_price_list 等

        内置重试策略：
        - error_code 30001（建议价过期）: 自动刷新建议价后重试一次
        - error_code 2002690（库存超限）: 去掉库存参数后重试一次
        """
        url = f"{BASE}/lakemms/enrollV2"
        body = {"activity_id": activity_id, "goods_volist": goods_volist}
        result = self.post(url, json_data=body, referer=ACT_REFERER)

        if not result:
            return None

        error_code = result.get("error_code")
        if error_code == 30001:
            logger.info("error_code=30001（建议价过期），尝试刷新建议价后重试...")
            goods_ids = [g.get("goods_id") for g in goods_volist if g.get("goods_id")]
            if goods_ids:
                self.get_suggest_prices(activity_id, goods_ids)
            return self.post(url, json_data=body, referer=ACT_REFERER)
        if error_code == 2002690:
            logger.info("error_code=2002690（库存超限），去掉库存参数后重试...")
            stripped = []
            for g in goods_volist:
                ng = dict(g)
                ng.pop("quantity", None)
                ng.pop("sku_quantity", None)
                stripped.append(ng)
            return self.post(url, json_data={"activity_id": activity_id,
                                             "goods_volist": stripped}, referer=ACT_REFERER)
        return result

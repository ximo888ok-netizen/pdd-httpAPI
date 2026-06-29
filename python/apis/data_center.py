# -*- coding: utf-8 -*-
"""数据中心 API（6 端点，来自 03_data_center.json）"""
from typing import Optional, Dict, Any
from base_request import BaseRequest

BASE = "https://mms.pinduoduo.com"
HOME_REFERER = "https://mms.pinduoduo.com/home"


class DataCenterAPI(BaseRequest):
    """数据中心接口"""

    def query_trade_list(self, query_type: int = 6,
                         query_date: str = "") -> Optional[Dict[str, Any]]:
        """交易趋势列表 → POST /sydney/api/mallTrade/queryMallTradeList

        Args:
            query_type: 查询类型（6=实时交易趋势）
            query_date: 查询日期（空=默认）
        """
        url = f"{BASE}/sydney/api/mallTrade/queryMallTradeList"
        return self.post(url, json_data={"queryType": query_type, "queryDate": query_date},
                         referer=HOME_REFERER)

    def query_mall_score(self) -> Optional[Dict[str, Any]]:
        """店铺 DSR 评分详情 → POST /sydney/api/mallScore/queryMallScoreInfo"""
        url = f"{BASE}/sydney/api/mallScore/queryMallScoreInfo"
        return self.post(url, data="", referer=HOME_REFERER)

    def query_sale_quality(self, query_date: str = "") -> Optional[Dict[str, Any]]:
        """售后品质指标 → POST /sydney/api/saleQuality/querySaleQualityDetailInfo

        Args:
            query_date: 查询日期
        """
        url = f"{BASE}/sydney/api/saleQuality/querySaleQualityDetailInfo"
        return self.post(url, json_data={"queryDate": query_date}, referer=HOME_REFERER)

    def query_not_pay_order(self) -> Optional[Dict[str, Any]]:
        """未付订单汇总 → POST /sydney/api/mallTrade/getMallNotPayOrderInfoV2"""
        url = f"{BASE}/sydney/api/mallTrade/getMallNotPayOrderInfoV2"
        return self.post(url, data="", referer=HOME_REFERER)

    def query_home_overview(self) -> Optional[Dict[str, Any]]:
        """首页经营概览 → POST /sydney/api/mallCoreData/homePageOverView"""
        url = f"{BASE}/sydney/api/mallCoreData/homePageOverView"
        return self.post(url, data="", referer=HOME_REFERER)

    def query_home_promotion_overview(self) -> Optional[Dict[str, Any]]:
        """首页推广概览 → POST /sydney/api/mallCoreData/homePagePromotionOverView"""
        url = f"{BASE}/sydney/api/mallCoreData/homePagePromotionOverView"
        return self.post(url, data="", referer=HOME_REFERER)

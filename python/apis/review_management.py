# -*- coding: utf-8 -*-
"""评价管理 API（6 端点，来自 04_review_management.json）"""
from typing import Optional, Dict, Any, List
from base_request import BaseRequest

BASE = "https://mms.pinduoduo.com"
REVIEW_REFERER = "https://mms.pinduoduo.com/reviews.html"


class ReviewAPI(BaseRequest):
    """评价管理接口"""

    def get_reviews_list(self, page_no: int = 1, page_size: int = 10,
                         start_time: Optional[int] = None, end_time: Optional[int] = None,
                         order_sn: str = None,
                         desc_score: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """评价列表 → POST /saturn/reviews/list

        Args:
            page_no: 页码（默认1）
            page_size: 每页条数（默认10）
            start_time: 开始时间（秒级时间戳，可空）
            end_time: 结束时间（秒级时间戳，可空）
            order_sn: 订单号筛选（可空）
            desc_score: 评分筛选（['1']差评, ['2']中评, ['3']好评）
        """
        url = f"{BASE}/saturn/reviews/list"
        data = {
            "startTime": start_time,
            "endTime": end_time,
            "pageNo": page_no,
            "pageSize": page_size,
            "orderSn": order_sn or "",
            "descScore": desc_score,
        }
        return self.post(url, json_data=data, referer=REVIEW_REFERER)

    def get_reviews_type_agg(self, range_type: int = 4) -> Optional[Dict[str, Any]]:
        """评价类型聚合统计（好评/中评/差评）→ POST /saturn/reviews/type/agg

        Args:
            range_type: 时间范围类型（4=近3个月）
        """
        url = f"{BASE}/saturn/reviews/type/agg"
        return self.post(url, json_data={"rangeType": range_type}, referer=REVIEW_REFERER)

    def get_reviews_keywords_agg(self, range_type: int = 4,
                                 start_time: Optional[int] = None,
                                 end_time: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """评价关键词聚合分析 → POST /saturn/reviews/keywords/agg"""
        url = f"{BASE}/saturn/reviews/keywords/agg"
        data = {
            "startTime": start_time,
            "endTime": end_time,
            "rangeType": range_type,
        }
        return self.post(url, json_data=data, referer=REVIEW_REFERER)

    def get_review_detail(self, review_id: str,
                          goods_id: str) -> Optional[Dict[str, Any]]:
        """评价详情 → POST /saturn/reviews/detail/info

        Args:
            review_id: 评价 ID
            goods_id: 商品 ID
        """
        url = f"{BASE}/saturn/reviews/detail/info"
        return self.post(url, json_data={"reviewId": review_id, "goodsId": goods_id},
                         referer=REVIEW_REFERER)

    def create_reported_review(self, review_id: str, report_type: str = "8",
                               picture_urls: Optional[List[str]] = None,
                               describes: str = "") -> Optional[Dict[str, Any]]:
        """举报违规评论 → POST /saturn/reportedReview/edit/createReportedReview

        Args:
            review_id: 评价 ID
            report_type: 举报类型（8=疑似同行恶意竞争）
            picture_urls: 举报图片 URL 列表
            describes: 举报描述
        """
        url = f"{BASE}/saturn/reportedReview/edit/createReportedReview"
        data = {
            "reviewId": review_id,
            "reportType": report_type,
            "pictureUrls": picture_urls or [],
            "describes": describes,
        }
        return self.post(url, json_data=data, referer=REVIEW_REFERER)

    def query_reported_review_num(self) -> Optional[Dict[str, Any]]:
        """查询已举报评论数量 → POST /saturn/reportedReview/query/queryTypesReportedReviewNum"""
        url = f"{BASE}/saturn/reportedReview/query/queryTypesReportedReviewNum"
        return self.post(url, data="", referer=REVIEW_REFERER)

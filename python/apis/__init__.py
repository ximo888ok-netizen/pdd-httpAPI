# -*- coding: utf-8 -*-
"""拼多多 API 端点封装模块"""
from .auth_shop import AuthShopAPI
from .customer_service import CustomerServiceAPI
from .data_center import DataCenterAPI
from .review_management import ReviewAPI
from .activity_enroll import ActivityEnrollAPI
from .product_management import ProductAPI

__all__ = [
    "AuthShopAPI",
    "CustomerServiceAPI",
    "DataCenterAPI",
    "ReviewAPI",
    "ActivityEnrollAPI",
    "ProductAPI",
]

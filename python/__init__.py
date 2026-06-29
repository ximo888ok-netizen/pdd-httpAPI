# -*- coding: utf-8 -*-
"""
拼多多商家后台 HTTP API 封装（Python 版）
==========================================
基于 pdd-httpAPI 目录下的 9 份 JSON 接口文档封装。
提供 SDK 类库（client.PDDClient）+ FastAPI Web 服务（server.app）。

快速开始:
    cd python
    pip install -r requirements.txt

    # SDK 用法
    python -c "from client import PDDClient; c = PDDClient(); print(c)"

    # Web 服务
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload
    # Swagger 文档: http://localhost:8000/docs
"""
from client import PDDClient
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

__all__ = [
    "PDDClient",
    "PDDAuth",
    "BaseRequest",
    "AuthShopAPI",
    "CustomerServiceAPI",
    "DataCenterAPI",
    "ReviewAPI",
    "ActivityEnrollAPI",
    "ProductAPI",
]

__version__ = "1.0.0"

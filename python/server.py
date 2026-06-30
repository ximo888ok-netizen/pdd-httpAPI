# -*- coding: utf-8 -*-
"""
拼多多 API FastAPI Web 服务
==========================
将所有 SDK 端点暴露为 REST API，支持多店铺。

启动:
    cd python
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload

Swagger 文档: http://localhost:8000/docs
"""
import logging
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from client import PDDClient

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("pdd_server")

app = FastAPI(
    title="拼多多商家后台 HTTP API",
    description="基于 pdd-httpAPI 文档封装的 REST API 服务，支持多店铺、扫码登录、Anti-Content 自动注入",
    version="1.0.0",
)

# 多店铺客户端缓存：mall_id -> PDDClient
_clients: Dict[str, PDDClient] = {}


def get_client(mall_id: str) -> PDDClient:
    """获取或创建某店铺的客户端实例"""
    if mall_id not in _clients:
        client = PDDClient(mall_id=mall_id, auto_login=True)
        if not client.cookies:
            raise HTTPException(status_code=401,
                                detail=f"店铺 {mall_id} 未登录或 cookies 已失效，请先登录")
        _clients[mall_id] = client
    return _clients[mall_id]


# ══════════════════════════════════════════════════════════════════════
# 通用响应模型
# ══════════════════════════════════════════════════════════════════════

class ApiResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    error: Optional[str] = None


def ok(data: Any) -> ApiResponse:
    return ApiResponse(success=True, data=data)


def fail(error: str) -> ApiResponse:
    return ApiResponse(success=False, error=error)


def call_api(data: Optional[Dict]) -> ApiResponse:
    """统一包装 SDK 返回结果"""
    if data is None:
        return fail("请求失败，请查看服务端日志")
    if isinstance(data, dict) and data.get("success") is False:
        return fail(data.get("errorMsg") or data.get("error_msg") or "接口返回失败")
    return ok(data)


# ══════════════════════════════════════════════════════════════════════
# 登录认证路由
# ══════════════════════════════════════════════════════════════════════

class LoginWaitRequest(BaseModel):
    timeout: int = 120


@app.post("/login/qrcode", response_model=ApiResponse, tags=["登录"])
def login_qrcode():
    """获取登录二维码 URL"""
    from auth import PDDAuth
    auth = PDDAuth()
    uri = auth.get_qrcode()
    if not uri:
        return fail("获取二维码失败")
    return ok({"qrcode_url": uri, "ticket": auth._ticket})


@app.get("/login/status", response_model=ApiResponse, tags=["登录"])
def login_status(ticket: str = Query(..., description="扫码 ticket")):
    """查询扫码状态（单次）"""
    from auth import PDDAuth
    auth = PDDAuth()
    result = auth.query_scan_status(ticket)
    return ok(result)


@app.post("/login/wait", response_model=ApiResponse, tags=["登录"])
def login_wait(body: LoginWaitRequest):
    """等待扫码登录完成（阻塞，超时后返回失败）"""
    # 注意：此接口需要先调用 /login/qrcode 获取 ticket
    # 这里使用一次性客户端完成登录
    from auth import PDDAuth
    auth = PDDAuth()
    # 需要重新获取二维码（无状态设计）
    uri = auth.get_qrcode()
    if not uri:
        return fail("获取二维码失败")
    result = auth.wait_for_scan(timeout=body.timeout)
    if not result:
        return fail("扫码登录超时或失败")
    mall_id = str(result["mall_id"])
    auth.save_cookies(mall_id, result["cookies"],
                      result.get("user_id"), result.get("username", ""))
    client = PDDClient(mall_id=mall_id, auto_login=True)
    _clients[mall_id] = client
    return ok({"mall_id": mall_id, "user_id": result.get("user_id"),
               "username": result.get("username", ""),
               "qrcode_url": uri})


# ══════════════════════════════════════════════════════════════════════
# 店铺管理路由
# ══════════════════════════════════════════════════════════════════════

@app.get("/malls", response_model=ApiResponse, tags=["店铺"])
def list_malls():
    """列出所有已登录店铺"""
    from auth import PDDAuth
    return ok(PDDAuth().list_malls())


@app.delete("/malls/{mall_id}", response_model=ApiResponse, tags=["店铺"])
def logout_mall(mall_id: str):
    """登出某店铺（删除 cookies）"""
    from auth import PDDAuth
    if mall_id in _clients:
        del _clients[mall_id]
    success = PDDAuth().logout(mall_id)
    return ok({"deleted": success})


# ══════════════════════════════════════════════════════════════════════
# 认证与店铺信息（01）
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/{mall_id}/auth/token", response_model=ApiResponse, tags=["认证与店铺"])
def auth_token(mall_id: str):
    return call_api(get_client(mall_id).auth_shop.get_token())


@app.post("/api/{mall_id}/auth/userinfo", response_model=ApiResponse, tags=["认证与店铺"])
def auth_userinfo(mall_id: str):
    return call_api(get_client(mall_id).auth_shop.get_user_info())


@app.post("/api/{mall_id}/auth/shop", response_model=ApiResponse, tags=["认证与店铺"])
def auth_shop(mall_id: str):
    return call_api(get_client(mall_id).auth_shop.get_shop_info())


class CsStatusRequest(BaseModel):
    status: int


@app.post("/api/{mall_id}/auth/csstatus", response_model=ApiResponse, tags=["认证与店铺"])
def auth_csstatus(mall_id: str, body: CsStatusRequest):
    return call_api(get_client(mall_id).auth_shop.set_csstatus(body.status))


# ══════════════════════════════════════════════════════════════════════
# 客服消息（02）
# ══════════════════════════════════════════════════════════════════════

class SendTextRequest(BaseModel):
    to_uid: str
    content: str


class SendImageRequest(BaseModel):
    to_uid: str
    image_url: str


class SendGoodsCardRequest(BaseModel):
    to_uid: str
    goods_id: int
    biz_type: int = 2


class MoveConversationRequest(BaseModel):
    uid: str
    cs_uid: str
    remark: str = "无原因直接转移"


@app.post("/api/{mall_id}/customer/send_text", response_model=ApiResponse, tags=["客服消息"])
def customer_send_text(mall_id: str, body: SendTextRequest):
    return call_api(get_client(mall_id).customer_service.send_text(body.to_uid, body.content))


@app.post("/api/{mall_id}/customer/send_image", response_model=ApiResponse, tags=["客服消息"])
def customer_send_image(mall_id: str, body: SendImageRequest):
    return call_api(get_client(mall_id).customer_service.send_image(body.to_uid, body.image_url))


@app.post("/api/{mall_id}/customer/send_goods_card", response_model=ApiResponse, tags=["客服消息"])
def customer_send_goods_card(mall_id: str, body: SendGoodsCardRequest):
    return call_api(get_client(mall_id).customer_service.send_goods_card(
        body.to_uid, body.goods_id, body.biz_type))


@app.get("/api/{mall_id}/customer/assign_cs_list", response_model=ApiResponse, tags=["客服消息"])
def customer_assign_cs_list(mall_id: str):
    return call_api(get_client(mall_id).customer_service.get_assign_cs_list())


@app.post("/api/{mall_id}/customer/move_conversation", response_model=ApiResponse, tags=["客服消息"])
def customer_move_conversation(mall_id: str, body: MoveConversationRequest):
    return call_api(get_client(mall_id).customer_service.move_conversation(
        body.uid, body.cs_uid, body.remark))


# ══════════════════════════════════════════════════════════════════════
# 数据中心（03）
# ══════════════════════════════════════════════════════════════════════

class TradeListRequest(BaseModel):
    query_type: int = 6
    query_date: str = ""


class SaleQualityRequest(BaseModel):
    query_date: str = ""


@app.post("/api/{mall_id}/data/trade_list", response_model=ApiResponse, tags=["数据中心"])
def data_trade_list(mall_id: str, body: TradeListRequest):
    return call_api(get_client(mall_id).data_center.query_trade_list(body.query_type, body.query_date))


@app.post("/api/{mall_id}/data/mall_score", response_model=ApiResponse, tags=["数据中心"])
def data_mall_score(mall_id: str):
    return call_api(get_client(mall_id).data_center.query_mall_score())


@app.post("/api/{mall_id}/data/sale_quality", response_model=ApiResponse, tags=["数据中心"])
def data_sale_quality(mall_id: str, body: SaleQualityRequest):
    return call_api(get_client(mall_id).data_center.query_sale_quality(body.query_date))


@app.post("/api/{mall_id}/data/not_pay_order", response_model=ApiResponse, tags=["数据中心"])
def data_not_pay_order(mall_id: str):
    return call_api(get_client(mall_id).data_center.query_not_pay_order())


@app.post("/api/{mall_id}/data/home_overview", response_model=ApiResponse, tags=["数据中心"])
def data_home_overview(mall_id: str):
    return call_api(get_client(mall_id).data_center.query_home_overview())


@app.post("/api/{mall_id}/data/home_promotion_overview", response_model=ApiResponse, tags=["数据中心"])
def data_home_promotion_overview(mall_id: str):
    return call_api(get_client(mall_id).data_center.query_home_promotion_overview())


# ══════════════════════════════════════════════════════════════════════
# 评价管理（04）
# ══════════════════════════════════════════════════════════════════════

class ReviewsListRequest(BaseModel):
    page_no: int = 1
    page_size: int = 10
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    order_sn: Optional[str] = None
    desc_score: Optional[List[str]] = None


class ReviewsAggRequest(BaseModel):
    range_type: int = 4


class ReviewsKeywordsRequest(BaseModel):
    range_type: int = 4
    start_time: Optional[int] = None
    end_time: Optional[int] = None


class ReviewDetailRequest(BaseModel):
    review_id: str
    goods_id: str


class ReportReviewRequest(BaseModel):
    review_id: str
    report_type: str = "8"
    picture_urls: List[str] = []
    describes: str = ""


@app.post("/api/{mall_id}/reviews/list", response_model=ApiResponse, tags=["评价管理"])
def reviews_list(mall_id: str, body: ReviewsListRequest):
    return call_api(get_client(mall_id).review.get_reviews_list(
        body.page_no, body.page_size, body.start_time, body.end_time,
        body.order_sn, body.desc_score))


@app.post("/api/{mall_id}/reviews/type_agg", response_model=ApiResponse, tags=["评价管理"])
def reviews_type_agg(mall_id: str, body: ReviewsAggRequest):
    return call_api(get_client(mall_id).review.get_reviews_type_agg(body.range_type))


@app.post("/api/{mall_id}/reviews/keywords_agg", response_model=ApiResponse, tags=["评价管理"])
def reviews_keywords_agg(mall_id: str, body: ReviewsKeywordsRequest):
    return call_api(get_client(mall_id).review.get_reviews_keywords_agg(
        body.range_type, body.start_time, body.end_time))


@app.post("/api/{mall_id}/reviews/detail", response_model=ApiResponse, tags=["评价管理"])
def reviews_detail(mall_id: str, body: ReviewDetailRequest):
    return call_api(get_client(mall_id).review.get_review_detail(body.review_id, body.goods_id))


@app.post("/api/{mall_id}/reviews/report", response_model=ApiResponse, tags=["评价管理"])
def reviews_report(mall_id: str, body: ReportReviewRequest):
    return call_api(get_client(mall_id).review.create_reported_review(
        body.review_id, body.report_type, body.picture_urls, body.describes))


@app.get("/api/{mall_id}/reviews/reported_num", response_model=ApiResponse, tags=["评价管理"])
def reviews_reported_num(mall_id: str):
    return call_api(get_client(mall_id).review.query_reported_review_num())


# ══════════════════════════════════════════════════════════════════════
# 活动报名（05）
# ══════════════════════════════════════════════════════════════════════

class ActivityDetailRequest(BaseModel):
    activity_id: int


class EligibleGoodsRequest(BaseModel):
    activity_id: int
    goods_id: Optional[int] = None
    goods_name: str = ""
    page: int = 1
    page_size: int = 10


class PriceRulesRequest(BaseModel):
    activity_id: int
    goods_id_list: List[int]


class EnrollRequest(BaseModel):
    activity_id: int
    goods_volist: List[Dict[str, Any]]


@app.post("/api/{mall_id}/activity/check_login", response_model=ApiResponse, tags=["活动报名"])
def activity_check_login(mall_id: str):
    return call_api(get_client(mall_id).activity.check_login())


@app.post("/api/{mall_id}/activity/detail", response_model=ApiResponse, tags=["活动报名"])
def activity_detail(mall_id: str, body: ActivityDetailRequest):
    return call_api(get_client(mall_id).activity.get_activity_detail(body.activity_id))


@app.post("/api/{mall_id}/activity/eligible_goods", response_model=ApiResponse, tags=["活动报名"])
def activity_eligible_goods(mall_id: str, body: EligibleGoodsRequest):
    return call_api(get_client(mall_id).activity.get_eligible_goods(
        body.activity_id, body.goods_id, body.goods_name, body.page, body.page_size))


@app.post("/api/{mall_id}/activity/price_rules", response_model=ApiResponse, tags=["活动报名"])
def activity_price_rules(mall_id: str, body: PriceRulesRequest):
    return call_api(get_client(mall_id).activity.get_price_rules(body.activity_id, body.goods_id_list))


@app.post("/api/{mall_id}/activity/suggest_prices", response_model=ApiResponse, tags=["活动报名"])
def activity_suggest_prices(mall_id: str, body: PriceRulesRequest):
    return call_api(get_client(mall_id).activity.get_suggest_prices(body.activity_id, body.goods_id_list))


@app.post("/api/{mall_id}/activity/enroll", response_model=ApiResponse, tags=["活动报名"])
def activity_enroll(mall_id: str, body: EnrollRequest):
    return call_api(get_client(mall_id).activity.do_enroll(body.activity_id, body.goods_volist))


# ══════════════════════════════════════════════════════════════════════
# 商品管理（06）
# ══════════════════════════════════════════════════════════════════════

class ProductListRequest(BaseModel):
    page: int = 1
    page_size: int = 20


class ProductDetailRequest(BaseModel):
    goods_id: int


class CreateDraftRequest(BaseModel):
    cat_id: int


class SaveDraftRequest(BaseModel):
    data: Dict[str, Any]


class SpuPropertiesRequest(BaseModel):
    goods_commit_id: str
    goods_id: int
    key_properties: List[Dict[str, Any]]


class DraftDetailRequest(BaseModel):
    goods_commit_id: str


class TemplateRequest(BaseModel):
    cat_id: int
    goods_commit_id: Optional[str] = None
    goods_id: Optional[int] = None


class PublishRulesRequest(BaseModel):
    cat_id: int


class BrandListRequest(BaseModel):
    cat_id: int
    keyword: str = ""


class SpecNamesRequest(BaseModel):
    cat_id: int


class CreateSpecValueRequest(BaseModel):
    parent_id: int
    name: str
    cat_id: int


class ThumbnailRequest(BaseModel):
    url: str
    width: int = 0
    height: int = 0
    if_cut: bool = False
    dx: int = 0
    dy: int = 0


class ImageDirsRequest(BaseModel):
    parent_dir_id: int = 0


class ImageFilesRequest(BaseModel):
    dir_id: int
    page: int = 1
    page_size: int = 20


class AiPropertiesRequest(BaseModel):
    image_url: str
    cat_id: int


class AiTitleRequest(BaseModel):
    image_url: str
    cat_name: str


class ListingRequest(BaseModel):
    goods_ids: List[int]
    online: bool = True


class DeleteRequest(BaseModel):
    goods_ids: List[int]


@app.post("/api/{mall_id}/product/list", response_model=ApiResponse, tags=["商品管理"])
def product_list(mall_id: str, body: ProductListRequest):
    return call_api(get_client(mall_id).product.get_product_list(body.page, body.page_size))


@app.post("/api/{mall_id}/product/detail", response_model=ApiResponse, tags=["商品管理"])
def product_detail(mall_id: str, body: ProductDetailRequest):
    return call_api(get_client(mall_id).product.get_product_detail(body.goods_id))


@app.get("/api/{mall_id}/product/categories/search", response_model=ApiResponse, tags=["商品管理"])
def product_categories_search(mall_id: str, keyword: str = Query(...)):
    return call_api(get_client(mall_id).product.search_categories(keyword))


@app.get("/api/{mall_id}/product/categories/detail", response_model=ApiResponse, tags=["商品管理"])
def product_categories_detail(mall_id: str, cat_id: int = Query(...)):
    return call_api(get_client(mall_id).product.get_category_detail(cat_id))


@app.get("/api/{mall_id}/product/categories/children", response_model=ApiResponse, tags=["商品管理"])
def product_categories_children(mall_id: str, parent_id: int = Query(...)):
    return call_api(get_client(mall_id).product.get_category_children(parent_id))


@app.get("/api/{mall_id}/product/categories/level1", response_model=ApiResponse, tags=["商品管理"])
def product_categories_level1(mall_id: str):
    return call_api(get_client(mall_id).product.get_level1_categories())


@app.post("/api/{mall_id}/product/draft/create", response_model=ApiResponse, tags=["商品管理"])
def product_draft_create(mall_id: str, body: CreateDraftRequest):
    return call_api(get_client(mall_id).product.create_draft(body.cat_id))


@app.post("/api/{mall_id}/product/draft/save", response_model=ApiResponse, tags=["商品管理"])
def product_draft_save(mall_id: str, body: SaveDraftRequest):
    return call_api(get_client(mall_id).product.save_draft(body.data))


@app.post("/api/{mall_id}/product/draft/spu_properties", response_model=ApiResponse, tags=["商品管理"])
def product_draft_spu(mall_id: str, body: SpuPropertiesRequest):
    return call_api(get_client(mall_id).product.save_spu_key_properties(
        body.goods_commit_id, body.goods_id, body.key_properties))


@app.post("/api/{mall_id}/product/draft/detail", response_model=ApiResponse, tags=["商品管理"])
def product_draft_detail(mall_id: str, body: DraftDetailRequest):
    return call_api(get_client(mall_id).product.get_draft_detail(body.goods_commit_id))


@app.post("/api/{mall_id}/product/template", response_model=ApiResponse, tags=["商品管理"])
def product_template(mall_id: str, body: TemplateRequest):
    return call_api(get_client(mall_id).product.get_publish_template(
        body.cat_id, body.goods_commit_id, body.goods_id))


@app.post("/api/{mall_id}/product/rules", response_model=ApiResponse, tags=["商品管理"])
def product_rules(mall_id: str, body: PublishRulesRequest):
    return call_api(get_client(mall_id).product.get_publish_rules(body.cat_id))


@app.post("/api/{mall_id}/product/brands", response_model=ApiResponse, tags=["商品管理"])
def product_brands(mall_id: str, body: BrandListRequest):
    return call_api(get_client(mall_id).product.get_brand_list(body.cat_id, body.keyword))


@app.post("/api/{mall_id}/product/spec_names", response_model=ApiResponse, tags=["商品管理"])
def product_spec_names(mall_id: str, body: SpecNamesRequest):
    return call_api(get_client(mall_id).product.query_spec_names(body.cat_id))


@app.post("/api/{mall_id}/product/spec_value", response_model=ApiResponse, tags=["商品管理"])
def product_spec_value(mall_id: str, body: CreateSpecValueRequest):
    return call_api(get_client(mall_id).product.create_spec_value(
        body.parent_id, body.name, body.cat_id))


@app.post("/api/{mall_id}/product/image/thumbnail", response_model=ApiResponse, tags=["商品管理"])
def product_image_thumbnail(mall_id: str, body: ThumbnailRequest):
    return call_api(get_client(mall_id).product.make_thumbnail(
        body.url, body.width, body.height, body.if_cut, body.dx, body.dy))


@app.post("/api/{mall_id}/product/image/dirs", response_model=ApiResponse, tags=["商品管理"])
def product_image_dirs(mall_id: str, body: ImageDirsRequest):
    return call_api(get_client(mall_id).product.list_image_dirs(body.parent_dir_id))


@app.post("/api/{mall_id}/product/image/files", response_model=ApiResponse, tags=["商品管理"])
def product_image_files(mall_id: str, body: ImageFilesRequest):
    return call_api(get_client(mall_id).product.list_image_files(
        body.dir_id, body.page, body.page_size))


@app.post("/api/{mall_id}/product/ai/properties", response_model=ApiResponse, tags=["商品管理"])
def product_ai_properties(mall_id: str, body: AiPropertiesRequest):
    return call_api(get_client(mall_id).product.ai_recommend_properties(body.image_url, body.cat_id))


@app.post("/api/{mall_id}/product/ai/title", response_model=ApiResponse, tags=["商品管理"])
def product_ai_title(mall_id: str, body: AiTitleRequest):
    return call_api(get_client(mall_id).product.ai_recommend_title(body.image_url, body.cat_name))


@app.post("/api/{mall_id}/product/listing", response_model=ApiResponse, tags=["商品管理"])
def product_listing(mall_id: str, body: ListingRequest):
    return call_api(get_client(mall_id).product.set_listing_status(body.goods_ids, body.online))


@app.post("/api/{mall_id}/product/delete", response_model=ApiResponse, tags=["商品管理"])
def product_delete(mall_id: str, body: DeleteRequest):
    return call_api(get_client(mall_id).product.delete_products(body.goods_ids))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

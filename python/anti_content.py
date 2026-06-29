# -*- coding: utf-8 -*-
"""
拼多多 Anti-Content 签名生成（Python 自包含版）
================================================
通过 execjs 调用外部 Anti-Content-pdd/res.js 生成签名。
不依赖项目内其他模块，仅依赖 PyExecJS + 外部 res.js。
"""
import logging
from pathlib import Path
from typing import Optional

try:
    import execjs
except ImportError:
    execjs = None

logger = logging.getLogger("anti_content")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

# res.js 路径：pdd-httpAPI/python/ → 上两级 → Anti-Content-pdd/res.js
_RES_JS_PATH = Path(__file__).resolve().parent.parent.parent / "Anti-Content-pdd" / "res.js"
_JS_CONTEXT = None

# Anti-Content 白名单（从 anti_content.js 的 requiresAntiContent 移植）
_WHITELIST = [
    '/apollo/',
    'glide/mms/goodsCommit/action/edit',
    'glide/v2/mms/edit/commit/submit',
    'glide/v2/mms/edit/commit/update',
    'vodka/v2/mms/pc/offSale',
    'vodka/v2/mms/batchOffSale',
    'vodka/v2/mms/pc/onSale',
    'vodka/v2/mms/batchOnSale',
    'vodka/v2/mms/antiRisk/verify',
    'janus/api/getCaptchaCode',
    'janus/api/scan/login/qrcode',
    'janus/api/scan/login/query',
    'sydney/api/saleQuality/querySaleQualityDetailInfo',
    'sydney/api/mallScore/getMallScore',
    'sydney/api/mallScore/queryMallScoreInfo',
    'sydney/api/mallTrade/queryMallTradeList',
    'sydney/api/mallCoreData/homePageOverView',
    'sydney/api/mallCoreData/homePagePromotionOverView',
    'saturn/reviews/list',
    'saturn/reviews/type/agg',
    'saturn/reviews/keywords/agg',
    'saturn/reviews/detail/info',
    'saturn/reportedReview/edit/createReportedReview',
    'leekmms/activity/query/detail',
    'leekmms/activity/query/eligible/goods/listV2',
    'leekmms/activity/query/enroll/rule_v3',
    'lakemms/enrollV2',
    'galerie/business/get_signature',
    'garner/mms/dir/dirListV2',
    'garner/mms/file/list',
    'glide/v2/mms/edit/commit/create_new',
    'glide/v2/mms/image/thumbnail',
    'glide/v2/mms/query/spec/name/list',
    'glide/v2/mms/query/spec/by/name',
    'glide/v2/mms/query/rules/limit/new',
    'glide/v2/mms/query/commit/detail',
    'glide/v2/mms/query/commit/on_shop/detail',
    'glide/mms/goodsCommit/action/edit_spu_key_properties',
    'draco-ms/mms/template/mall',
    'draco-ms/mms/brand/audit/record',
    'witcher/api/properties-recommender-by-img',
    'witcher/api/rec-goods-title',
    'plateau/chat/send_message',
    'plateau/message/send/mallGoodsCard',
    'plateau/chat/move_conversation',
    'plateau/chat/set_csstatus',
    'latitude/assign/getAssignCsList',
    'latitude/goods/recommendGoods',
    'janus/api/new/userinfo',
    'janus/api/subSystem/getAuthToken',
    'earth/api/merchant/queryMerchantInfoByMallId',
    'chats/getToken',
    'leekmms/activity/query/enroll/rule_suggest_price',
]


def _load_js():
    """加载并编译 res.js（懒加载，只执行一次）"""
    global _JS_CONTEXT
    if _JS_CONTEXT is not None:
        return _JS_CONTEXT
    if execjs is None:
        raise ImportError("PyExecJS 未安装，请执行: pip install PyExecJS")
    if not _RES_JS_PATH.exists():
        raise FileNotFoundError(f"res.js 不存在: {_RES_JS_PATH}")
    with open(_RES_JS_PATH, "r", encoding="utf-8") as f:
        _JS_CONTEXT = execjs.compile(f.read())
    logger.info("res.js 加载成功: %s", _RES_JS_PATH)
    return _JS_CONTEXT


def generate_anti_content(user_agent: Optional[str] = None) -> str:
    """
    生成拼多多 MMS Anti-Content 签名。

    Args:
        user_agent: 浏览器 UA，默认 DEFAULT_USER_AGENT

    Returns:
        Anti-Content 字符串（base64）
    """
    ctx = _load_js()
    if user_agent is None:
        user_agent = DEFAULT_USER_AGENT
    try:
        return ctx.call("getAntiContent", user_agent)
    except Exception as e:
        logger.error("生成 anti-content 失败: %s", e)
        return ""


def requires_anti_content(endpoint: str) -> bool:
    """检查指定端点是否需要 Anti-Content 头"""
    if not endpoint:
        return False
    lower = endpoint.lower()
    return any(p.lower() in lower for p in _WHITELIST)


if __name__ == "__main__":
    ac = generate_anti_content()
    print(f"Anti-Content ({len(ac)} chars): {ac[:80]}...")

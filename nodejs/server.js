'use strict';
/**
 * 拼多多 API 原生 http Web 服务（Node.js 版）
 * ============================================
 * 零第三方依赖，仅用 Node.js 内置 http 模块。
 * 路由结构与 Python FastAPI 版完全一致（仅端口不同：8001）。
 *
 * 启动:
 *   cd nodejs
 *   node server.js
 *   # 访问 http://localhost:8001/
 */
const http = require('http');
const { URL } = require('url');
const { PDDClient } = require('./client');
const { PDDAuth } = require('./auth');

const PORT = 8001;
const _clients = {};

function getClient(mallId) {
    if (!_clients[mallId]) {
        const client = new PDDClient({ mallId, autoLogin: true });
        if (!client.cookies || !Object.keys(client.cookies).length) {
            const err = new Error(`店铺 ${mallId} 未登录或 cookies 已失效`);
            err.code = 401;
            throw err;
        }
        _clients[mallId] = client;
    }
    return _clients[mallId];
}

function ok(data) { return { success: true, data }; }
function fail(error) { return { success: false, error }; }

async function callApi(promise) {
    try {
        const data = await promise;
        if (data === null || data === undefined) return fail('请求失败，请查看服务端日志');
        if (data && data.success === false) {
            return fail(data.errorMsg || data.error_msg || '接口返回失败');
        }
        return ok(data);
    } catch (e) {
        return fail(e.message);
    }
}

// ── 路由表 ──────────────────────────────────────────────────────────
// 每项: [method, pattern, handler(req) -> result]
// pattern 中 :param 会提取到 req.params
const routes = [];

function route(method, pattern, handler) {
    const keys = [];
    const re = new RegExp('^' + pattern.replace(/:([^/]+)/g, (_, k) => { keys.push(k); return '([^/]+)'; }) + '$');
    routes.push({ method, re, keys, handler });
}

function matchRoute(method, pathname) {
    for (const r of routes) {
        if (r.method !== method) continue;
        const m = r.re.exec(pathname);
        if (m) {
            const params = {};
            r.keys.forEach((k, i) => { params[k] = decodeURIComponent(m[i + 1]); });
            return { handler: r.handler, params };
        }
    }
    return null;
}

function readBody(req) {
    return new Promise((resolve) => {
        let chunks = '';
        req.on('data', d => chunks += d);
        req.on('end', () => {
            if (!chunks) return resolve({});
            try { resolve(JSON.parse(chunks)); } catch (e) { resolve({}); }
        });
    });
}

// ══════════════════════════════════════════════════════════════════════
// 登录认证
// ══════════════════════════════════════════════════════════════════════
route('POST', '/login/qrcode', async () => {
    const auth = new PDDAuth();
    const uri = await auth.getQrcode();
    if (!uri) return fail('获取二维码失败');
    return ok({ qrcode_url: uri, ticket: auth._ticket });
});

route('GET', '/login/status', async (req) => {
    const auth = new PDDAuth();
    const result = await auth.queryScanStatus(req.query.ticket);
    return ok(result);
});

route('POST', '/login/wait', async (req) => {
    const auth = new PDDAuth();
    const uri = await auth.getQrcode();
    if (!uri) return fail('获取二维码失败');
    const timeout = (req.body && req.body.timeout) || 120;
    const result = await auth.waitForScan(timeout);
    if (!result) return fail('扫码登录超时或失败');
    const mallId = String(result.mall_id);
    auth.saveCookies(mallId, result.cookies, result.user_id, result.username);
    _clients[mallId] = new PDDClient({ mallId, autoLogin: true });
    return ok({ mall_id: mallId, user_id: result.user_id, username: result.username, qrcode_url: uri });
});

// ══════════════════════════════════════════════════════════════════════
// 店铺管理
// ══════════════════════════════════════════════════════════════════════
route('GET', '/malls', async () => ok(new PDDAuth().listMalls()));

route('DELETE', '/malls/:mallId', async (req) => {
    const mallId = req.params.mallId;
    if (_clients[mallId]) delete _clients[mallId];
    return ok({ deleted: new PDDAuth().logout(mallId) });
});

// ══════════════════════════════════════════════════════════════════════
// 认证与店铺信息（01）
// ══════════════════════════════════════════════════════════════════════
const A = (mallId) => getClient(mallId).authShop;
route('POST', '/api/:mallId/auth/token', async (r) => callApi(A(r.params.mallId).getToken()));
route('POST', '/api/:mallId/auth/userinfo', async (r) => callApi(A(r.params.mallId).getUserInfo()));
route('POST', '/api/:mallId/auth/shop', async (r) => callApi(A(r.params.mallId).getShopInfo()));
route('POST', '/api/:mallId/auth/csstatus', async (r) => callApi(A(r.params.mallId).setCsstatus(r.body.status)));

// ══════════════════════════════════════════════════════════════════════
// 客服消息（02）
// ══════════════════════════════════════════════════════════════════════
const C = (mallId) => getClient(mallId).customerService;
route('POST', '/api/:mallId/customer/send_text', async (r) => callApi(C(r.params.mallId).sendText(r.body.to_uid, r.body.content)));
route('POST', '/api/:mallId/customer/send_image', async (r) => callApi(C(r.params.mallId).sendImage(r.body.to_uid, r.body.image_url)));
route('POST', '/api/:mallId/customer/send_goods_card', async (r) => callApi(C(r.params.mallId).sendGoodsCard(r.body.to_uid, r.body.goods_id, r.body.biz_type)));
route('GET', '/api/:mallId/customer/assign_cs_list', async (r) => callApi(C(r.params.mallId).getAssignCsList()));
route('POST', '/api/:mallId/customer/move_conversation', async (r) => callApi(C(r.params.mallId).moveConversation(r.body.uid, r.body.cs_uid, r.body.remark)));

// ══════════════════════════════════════════════════════════════════════
// 数据中心（03）
// ══════════════════════════════════════════════════════════════════════
const D = (mallId) => getClient(mallId).dataCenter;
route('POST', '/api/:mallId/data/trade_list', async (r) => callApi(D(r.params.mallId).queryTradeList(r.body.query_type, r.body.query_date)));
route('POST', '/api/:mallId/data/mall_score', async (r) => callApi(D(r.params.mallId).queryMallScore()));
route('POST', '/api/:mallId/data/sale_quality', async (r) => callApi(D(r.params.mallId).querySaleQuality(r.body.query_date)));
route('POST', '/api/:mallId/data/not_pay_order', async (r) => callApi(D(r.params.mallId).queryNotPayOrder()));
route('POST', '/api/:mallId/data/home_overview', async (r) => callApi(D(r.params.mallId).queryHomeOverview()));
route('POST', '/api/:mallId/data/home_promotion_overview', async (r) => callApi(D(r.params.mallId).queryHomePromotionOverview()));

// ══════════════════════════════════════════════════════════════════════
// 评价管理（04）
// ══════════════════════════════════════════════════════════════════════
const R = (mallId) => getClient(mallId).review;
route('POST', '/api/:mallId/reviews/list', async (r) => callApi(R(r.params.mallId).getReviewsList(r.body)));
route('POST', '/api/:mallId/reviews/type_agg', async (r) => callApi(R(r.params.mallId).getReviewsTypeAgg(r.body.range_type)));
route('POST', '/api/:mallId/reviews/keywords_agg', async (r) => callApi(R(r.params.mallId).getReviewsKeywordsAgg(r.body)));
route('POST', '/api/:mallId/reviews/detail', async (r) => callApi(R(r.params.mallId).getReviewDetail(r.body.review_id, r.body.goods_id)));
route('POST', '/api/:mallId/reviews/report', async (r) => callApi(R(r.params.mallId).createReportedReview(r.body.review_id, r.body.report_type, r.body.picture_urls, r.body.describes)));
route('GET', '/api/:mallId/reviews/reported_num', async (r) => callApi(R(r.params.mallId).queryReportedReviewNum()));

// ══════════════════════════════════════════════════════════════════════
// 活动报名（05）
// ══════════════════════════════════════════════════════════════════════
const AC = (mallId) => getClient(mallId).activity;
route('POST', '/api/:mallId/activity/check_login', async (r) => callApi(AC(r.params.mallId).checkLogin()));
route('POST', '/api/:mallId/activity/detail', async (r) => callApi(AC(r.params.mallId).getActivityDetail(r.body.activity_id)));
route('POST', '/api/:mallId/activity/eligible_goods', async (r) => callApi(AC(r.params.mallId).getEligibleGoods(r.body.activity_id, r.body)));
route('POST', '/api/:mallId/activity/price_rules', async (r) => callApi(AC(r.params.mallId).getPriceRules(r.body.activity_id, r.body.goods_id_list)));
route('POST', '/api/:mallId/activity/suggest_prices', async (r) => callApi(AC(r.params.mallId).getSuggestPrices(r.body.activity_id, r.body.goods_id_list)));
route('POST', '/api/:mallId/activity/enroll', async (r) => callApi(AC(r.params.mallId).doEnroll(r.body.activity_id, r.body.goods_volist)));

// ══════════════════════════════════════════════════════════════════════
// 商品管理（06）
// ══════════════════════════════════════════════════════════════════════
const P = (mallId) => getClient(mallId).product;
route('POST', '/api/:mallId/product/list', async (r) => callApi(P(r.params.mallId).getProductList(r.body.page, r.body.page_size)));
route('POST', '/api/:mallId/product/detail', async (r) => callApi(P(r.params.mallId).getProductDetail(r.body.goods_id)));
route('GET', '/api/:mallId/product/categories/search', async (r) => callApi(P(r.params.mallId).searchCategories(r.query.keyword)));
route('GET', '/api/:mallId/product/categories/detail', async (r) => callApi(P(r.params.mallId).getCategoryDetail(Number(r.query.cat_id))));
route('GET', '/api/:mallId/product/categories/children', async (r) => callApi(P(r.params.mallId).getCategoryChildren(Number(r.query.parent_id))));
route('GET', '/api/:mallId/product/categories/level1', async (r) => callApi(P(r.params.mallId).getLevel1Categories()));
route('POST', '/api/:mallId/product/draft/create', async (r) => callApi(P(r.params.mallId).createDraft(r.body.cat_id)));
route('POST', '/api/:mallId/product/draft/save', async (r) => callApi(P(r.params.mallId).saveDraft(r.body.data)));
route('POST', '/api/:mallId/product/draft/spu_properties', async (r) => callApi(P(r.params.mallId).saveSpuKeyProperties(r.body.goods_commit_id, r.body.goods_id, r.body.key_properties)));
route('POST', '/api/:mallId/product/draft/detail', async (r) => callApi(P(r.params.mallId).getDraftDetail(r.body.goods_commit_id)));
route('POST', '/api/:mallId/product/template', async (r) => callApi(P(r.params.mallId).getPublishTemplate(r.body.cat_id, r.body.goods_commit_id, r.body.goods_id)));
route('POST', '/api/:mallId/product/rules', async (r) => callApi(P(r.params.mallId).getPublishRules(r.body.cat_id)));
route('POST', '/api/:mallId/product/brands', async (r) => callApi(P(r.params.mallId).getBrandList(r.body.cat_id, r.body.keyword)));
route('POST', '/api/:mallId/product/spec_names', async (r) => callApi(P(r.params.mallId).querySpecNames(r.body.cat_id)));
route('POST', '/api/:mallId/product/spec_value', async (r) => callApi(P(r.params.mallId).createSpecValue(r.body.parent_id, r.body.name, r.body.cat_id)));
route('POST', '/api/:mallId/product/image/thumbnail', async (r) => callApi(P(r.params.mallId).makeThumbnail(r.body.url, r.body.width, r.body.height, r.body.if_cut, r.body.dx, r.body.dy)));
route('POST', '/api/:mallId/product/image/dirs', async (r) => callApi(P(r.params.mallId).listImageDirs(r.body.parent_dir_id)));
route('POST', '/api/:mallId/product/image/files', async (r) => callApi(P(r.params.mallId).listImageFiles(r.body.dir_id, r.body.page, r.body.page_size)));
route('POST', '/api/:mallId/product/ai/properties', async (r) => callApi(P(r.params.mallId).aiRecommendProperties(r.body.image_url, r.body.cat_id)));
route('POST', '/api/:mallId/product/ai/title', async (r) => callApi(P(r.params.mallId).aiRecommendTitle(r.body.image_url, r.body.cat_name)));
route('POST', '/api/:mallId/product/listing', async (r) => callApi(P(r.params.mallId).setListingStatus(r.body.goods_ids, r.body.online)));
route('POST', '/api/:mallId/product/delete', async (r) => callApi(P(r.params.mallId).deleteProducts(r.body.goods_ids)));

// ══════════════════════════════════════════════════════════════════════
// HTTP 服务
// ══════════════════════════════════════════════════════════════════════

const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, `http://localhost:${PORT}`);
    const pathname = u.pathname;
    const query = {};
    for (const [k, v] of u.searchParams.entries()) query[k] = v;

    if (pathname === '/' || pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ service: 'pdd-httpapi-nodejs', port: PORT, routes: routes.length }));
        return;
    }

    const matched = matchRoute(req.method, pathname);
    if (!matched) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: false, error: `路由不存在: ${req.method} ${pathname}` }));
        return;
    }

    const body = (req.method === 'POST' || req.method === 'PUT') ? await readBody(req) : {};
    try {
        const result = await matched.handler({ params: matched.params, query, body });
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
    } catch (e) {
        const code = e.code === 401 ? 401 : 500;
        res.writeHead(code, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: false, error: e.message }));
    }
});

server.listen(PORT, () => {
    console.log(`═`.repeat(60));
    console.log(`拼多多 HTTP API 服务 (Node.js) 已启动`);
    console.log(`═`.repeat(60));
    console.log(`监听: http://localhost:${PORT}`);
    console.log(`路由数: ${routes.length}`);
    console.log(`健康检查: http://localhost:${PORT}/health`);
    console.log(`─`.repeat(60));
});

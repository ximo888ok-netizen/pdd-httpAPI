#!/usr/bin/env node
/**
 * 拼多多 Anti-Content 签名生成器 (Node.js 版)
 * ============================================
 *
 * 基于 Anti-Content-pdd/res.js 核心算法，用 Node.js 原生 vm 模块执行，
 * 无需 PyExecJS / Python 环境，纯 Node.js 即可生成有效的 Anti-Content 签名。
 *
 * 用法:
 *   1. 作为模块:
 *      const { generateAntiContent } = require('./anti_content');
 *      const ac = generateAntiContent();                    // 默认 UA
 *      const ac = generateAntiContent('你的User-Agent');     // 自定义 UA
 *
 *   2. 命令行:
 *      node anti_content.js                  # 使用默认 UA
 *      node anti_content.js "自定义UA"        # 指定 UA
 *
 * 依赖: 无第三方依赖（仅使用 Node.js 内置 vm 模块）
 *
 * 算法来源: Anti-Content-pdd/res.js (gitbenxing/anti-content)
 * 算法流程:
 *   1. 设置 navigator.userAgent
 *   2. 加载 fbeZ webpack 模块
 *   3. 实例化 AntiContent 类 → 采集浏览器指纹
 *   4. updateServerTime(timestamp) → 注入时间戳
 *   5. messagePack() → 序列化 + SHA1 + base64 编码
 *   6. 返回 base64 签名字符串
 */

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ── 常量 ─────────────────────────────────────────────────────────────

/**
 * res.js 核心算法文件路径
 * 相对于本文件位置: anti-content/res.js
 */
const RES_JS_PATH = path.resolve(__dirname, 'anti-content', 'res.js');

/**
 * 统一 User-Agent（与 Python 版 anti_content.py 保持一致）
 */
const DEFAULT_USER_AGENT =
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
    'AppleWebKit/537.36 (KHTML, like Gecko) ' +
    'Chrome/137.0.0.0 Safari/537.36';

// ── 核心实现 ─────────────────────────────────────────────────────────

/**
 * VM 上下文缓存（避免每次调用都重新加载 594KB 的 res.js）
 * @type {vm.Context|null}
 */
let _vmContext = null;

/**
 * 加载 res.js 到 VM 上下文（懒加载，只执行一次）
 *
 * res.js 文件头部自带浏览器环境模拟（window/navigator/document/screen 等），
 * 使其可以在 Node.js 环境中直接运行。
 *
 * @returns {vm.Context} 已编译的 VM 上下文
 */
function loadContext() {
    if (_vmContext !== null) {
        return _vmContext;
    }

    if (!fs.existsSync(RES_JS_PATH)) {
        throw new Error(`res.js 不存在: ${RES_JS_PATH}`);
    }

    const resJsCode = fs.readFileSync(RES_JS_PATH, 'utf-8');

    // 创建 VM 沙箱上下文
    // res.js 内部会自行设置 window / navigator / document / screen 等对象
    const sandbox = {
        // console 供 res.js 内部 console.log 调试使用
        console: {
            log: () => {},   // 静默 res.js 内部的调试日志
            error: console.error,
            warn: console.warn,
        },
        // setTimeout / setInterval 供 webpack 模块系统使用
        setTimeout: setTimeout,
        setInterval: setInterval,
        clearTimeout: clearTimeout,
        clearInterval: clearInterval,
        // Date 供时间戳生成使用
        Date: Date,
        // JSON 供序列化使用
        JSON: JSON,
        // Math 供加密计算使用
        Math: Math,
        // Buffer (某些 polyfill 可能需要)
        Buffer: Buffer,
    };

    _vmContext = vm.createContext(sandbox);

    // 在 VM 上下文中执行 res.js
    // res.js 执行后会注册 window.sj 和全局 getAntiContent 函数
    vm.runInContext(resJsCode, _vmContext);

    return _vmContext;
}

/**
 * 生成拼多多 MMS Anti-Content 签名
 *
 * @param {string} [userAgent] - 浏览器 UA，默认使用 DEFAULT_USER_AGENT
 * @param {Object} [options] - 可选参数（预留扩展）
 * @param {string} [options.nanoFp] - 设备指纹 _nano_fp 值（预留）
 * @param {string} [options.cookieStr] - 完整 cookie 字符串（预留）
 * @param {string} [options.referrer] - 页面来源 URL（预留）
 * @param {string} [options.locationHref] - 当前页面 URL（预留）
 * @returns {string} Anti-Content 签名字符串（base64 编码）
 *
 * @example
 * const ac = generateAntiContent();
 * // => "0asAfa5E-wCEgx_M4Zir2chV7vB_dF2HezRW..."
 *
 * @example
 * const ac = generateAntiContent('Mozilla/5.0 ...');
 */
function generateAntiContent(userAgent, options) {
    const ctx = loadContext();

    if (!userAgent) {
        userAgent = DEFAULT_USER_AGENT;
    }

    // 调用 res.js 中的 getAntiContent(ua) 函数
    // 该函数内部:
    //   1. window.navigator.userAgent = ua
    //   2. window.sj('fbeZ') 加载 webpack 模块
    //   3. new anti() 实例化 → 采集指纹 (屏幕/navigator/时区等)
    //   4. res.updateServerTime(Date.now()) 注入时间戳
    //   5. res.messagePack() → SHA1 + base64 编码
    const anti = ctx.getAntiContent(userAgent);
    return anti;
}

/**
 * 批量生成 Anti-Content（每个调用独立时间戳）
 *
 * @param {number} count - 生成数量
 * @param {string} [userAgent] - 浏览器 UA
 * @returns {string[]} Anti-Content 签名字符串数组
 */
function generateBatch(count, userAgent) {
    const results = [];
    for (let i = 0; i < count; i++) {
        results.push(generateAntiContent(userAgent));
    }
    return results;
}

/**
 * 从 res.js 白名单中检查指定端点是否需要 Anti-Content
 *
 * res.js 第 1547 行定义了需要 Anti-Content 的端点白名单数组 (yt)，
 * 仅这些端点的请求需要携带 anti-content 头。
 *
 * @param {string} endpoint - API 端点路径（如 "/glide/mms/goodsCommit/action/edit"）
 * @returns {boolean} 是否需要 Anti-Content
 */
function requiresAntiContent(endpoint) {
    if (!endpoint) return false;

    // res.js 白名单中的端点（从源码提取，约 170+ 个）
    // 完整列表见 res.js 第 1547 行 yt 变量
    const whitelist = [
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
        'saturn/reportedReview/query/queryTypesReportedReviewNum',
        // 完整白名单请参考 res.js 源码第 1547 行
    ];

    const lower = endpoint.toLowerCase();
    return whitelist.some(function (pattern) {
        return lower.indexOf(pattern.toLowerCase()) >= 0;
    });
}

// ── 导出 ─────────────────────────────────────────────────────────────

module.exports = {
    generateAntiContent,
    generateBatch,
    requiresAntiContent,
    DEFAULT_USER_AGENT,
    RES_JS_PATH,

    // 暴露内部方法供高级用途
    loadContext,
};

// ── 命令行入口 ───────────────────────────────────────────────────────

if (require.main === module) {
    const args = process.argv.slice(2);
    const ua = args[0] || null;

    console.log('═'.repeat(60));
    console.log('拼多多 Anti-Content 签名生成器 (Node.js)');
    console.log('═'.repeat(60));
    console.log(`res.js: ${RES_JS_PATH}`);
    console.log(`UA: ${ua || DEFAULT_USER_AGENT}`);
    console.log('─'.repeat(60));

    try {
        const ac = generateAntiContent(ua);
        console.log(`\nAnti-Content (${ac.length} chars):`);
        console.log(ac);
        console.log('');
        console.log('─'.repeat(60));
        console.log('✅ 生成成功');
    } catch (e) {
        console.error(`\n❌ 生成失败: ${e.message}`);
        console.error(e.stack);
        process.exit(1);
    }
}

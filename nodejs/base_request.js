'use strict';
/**
 * 拼多多 API 请求基类（Node.js 自包含版）
 * ============================================
 * 零第三方依赖，仅用 Node.js 内置 https/http 模块。
 * 提供：重试机制、域名节流、Anti-Content 自动注入、cookies 管理。
 */
const https = require('https');
const http = require('http');
const { URL } = require('url');
const { generateAntiContent, requiresAntiContent, DEFAULT_USER_AGENT } = require('./anti_content');

// ── 全局频率控制（按域名） ──────────────────────────────────────────
const _lastRequestTime = {};
const _DOMAIN_INTERVALS = { 'mms.pinduoduo.com': 0.8 };
const _DEFAULT_MIN_INTERVAL = 0.5;
const _SENSITIVE_KEYS = ['password', 'cookies', 'token', 'api_key', 'access_token', 'anti-content', 'anti_content'];

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function sanitize(data) {
    if (!data || typeof data !== 'object') return data;
    const result = {};
    const sensitiveSet = new Set(_SENSITIVE_KEYS.map(s => s.toLowerCase()));
    for (const k of Object.keys(data)) {
        const lk = k.toLowerCase();
        if (sensitiveSet.has(lk)) {
            result[k] = '***';
        } else if (typeof data[k] === 'object' && data[k] !== null) {
            result[k] = Array.isArray(data[k]) ? data[k].map(sanitize) : sanitize(data[k]);
        } else {
            result[k] = data[k];
        }
    }
    return result;
}

class BaseRequest {
    /**
     * @param {Object} opts
     * @param {Object} [opts.cookies] - cookies 字典
     * @param {string} [opts.mallId] - 店铺 ID
     * @param {number} [opts.maxRetries=3]
     * @param {number} [opts.minInterval=0.5] - 最小请求间隔（秒）
     * @param {boolean} [opts.autoRelogin=false]
     * @param {Function} [opts.reloginCallback]
     */
    constructor(opts = {}) {
        this.cookies = opts.cookies || {};
        this.mallId = opts.mallId || null;
        this.maxRetries = opts.maxRetries != null ? opts.maxRetries : 3;
        this.retryDelay = opts.retryDelay || 1.0;
        this.retryBackoff = opts.retryBackoff || 2.0;
        this.minInterval = opts.minInterval != null ? opts.minInterval : 0.5;
        this.autoRelogin = !!opts.autoRelogin;
        this._reloginCallback = opts.reloginCallback || null;
        this._reloginAttempted = false;

        this.defaultHeaders = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://mms.pinduoduo.com',
            'user-agent': DEFAULT_USER_AGENT,
            'priority': 'u=1, i',
        };
    }

    // ── 请求头构建 ──────────────────────────────────────────────────

    _buildHeaders(url, referer, extra) {
        const headers = Object.assign({}, this.defaultHeaders);
        headers['referer'] = referer || 'https://mms.pinduoduo.com/';
        if (url && requiresAntiContent(url)) {
            try {
                const ac = generateAntiContent();
                if (ac) headers['anti-content'] = ac;
            } catch (e) {
                console.warn('[anti_content] 生成失败:', e.message);
            }
        }
        if (this.cookies && Object.keys(this.cookies).length) {
            headers['cookie'] = Object.entries(this.cookies).map(([k, v]) => `${k}=${v}`).join('; ');
        }
        if (extra) Object.assign(headers, extra);
        return headers;
    }

    // ── 频率控制 ────────────────────────────────────────────────────

    async _rateLimit(url) {
        if (!this.minInterval || !url) return;
        let domain;
        try { domain = new URL(url).hostname || ''; } catch (e) { return; }
        if (!domain) return;
        const interval = _DOMAIN_INTERVALS[domain] != null ? _DOMAIN_INTERVALS[domain] : this.minInterval;
        if (interval <= 0) return;
        const now = Date.now();
        const last = _lastRequestTime[domain] || 0;
        const wait = interval * 1000 - (now - last);
        if (wait > 0) await sleep(wait);
        _lastRequestTime[domain] = Date.now();
    }

    // ── 底层请求 ────────────────────────────────────────────────────

    _rawRequest(method, url, { params, body, referer, headers, timeout = 30000, _redirectCount = 0 } = {}) {
        const MAX_REDIRECTS = 5;
        return new Promise((resolve, reject) => {
            let fullUrl = url;
            if (params && Object.keys(params).length) {
                const qs = new URLSearchParams();
                for (const [k, v] of Object.entries(params)) qs.append(k, String(v));
                fullUrl += (url.includes('?') ? '&' : '?') + qs.toString();
            }
            const u = new URL(fullUrl);
            const lib = u.protocol === 'https:' ? https : http;
            const mergedHeaders = this._buildHeaders(url, referer, headers);
            let payload = null;
            if (body != null) {
                payload = typeof body === 'string' ? body : JSON.stringify(body);
                mergedHeaders['content-length'] = Buffer.byteLength(payload);
            }
            const reqOpts = {
                method,
                hostname: u.hostname,
                port: u.port || (u.protocol === 'https:' ? 443 : 80),
                path: u.pathname + u.search,
                headers: mergedHeaders,
                timeout,
            };
            const req = lib.request(reqOpts, (res) => {
                const redirectCodes = [301, 302, 307, 308];
                if (redirectCodes.includes(res.statusCode) && _redirectCount < MAX_REDIRECTS) {
                    const location = res.headers['location'];
                    if (location) {
                        const nextUrl = new URL(location, fullUrl).href;
                        const nextMethod = (res.statusCode === 307 || res.statusCode === 308) ? method : 'GET';
                        const nextBody = nextMethod === 'GET' || nextMethod === 'HEAD' ? null : body;
                        this._rawRequest(nextMethod, nextUrl, { body: nextBody, referer, headers, timeout, _redirectCount: _redirectCount + 1 })
                            .then(resolve, reject);
                        return;
                    }
                }
                let chunks = '';
                res.on('data', d => chunks += d);
                res.on('end', () => {
                    resolve({ status_code: res.statusCode, text: chunks, headers: res.headers });
                });
            });
            req.on('error', reject);
            req.on('timeout', () => { req.destroy(new Error('请求超时')); });
            if (payload) req.write(payload);
            req.end();
        });
    }

    // ── 重试机制 ────────────────────────────────────────────────────

    _shouldRetry(statusCode, exception) {
        if (exception) return true;
        if (statusCode >= 500) return true;
        if ([429, 408, 502, 503, 504].includes(statusCode)) return true;
        return false;
    }

    _calcRetryDelay(attempt) {
        const base = this.retryDelay * Math.pow(this.retryBackoff, attempt);
        const jitter = (0.1 + Math.random() * 0.2) * base;
        return (base + jitter) * 1000;
    }

    _isSessionExpired(data) {
        if (!data) return false;
        return data.error_code === 43001 && String(data.error_msg || '').includes('会话已过期');
    }

    async _executeWithRetry(requestFn, url) {
        let lastErr = null;
        let lastResp = null;
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                if (attempt === 0 && url) await this._rateLimit(url);
                const resp = await requestFn();
                if (resp.status_code === 200) {
                    let data = null;
                    try { data = JSON.parse(resp.text); } catch (e) {
                        console.error('[JSON] 解析失败:', resp.text.slice(0, 300));
                        return null;
                    }
                    if (this._isSessionExpired(data) && !this._reloginAttempted &&
                        this.autoRelogin && this._reloginCallback) {
                        console.info('[session] 检测到会话过期，尝试重新登录...');
                        this._reloginAttempted = true;
                        const newCookies = await this._reloginCallback(this.mallId);
                        if (newCookies) { this.updateCookies(newCookies); continue; }
                    }
                    return data;
                }
                lastResp = resp;
                if (attempt < this.maxRetries && this._shouldRetry(resp.status_code)) {
                    const delay = this._calcRetryDelay(attempt);
                    console.warn(`[retry] status=${resp.status_code}，第 ${attempt + 1} 次重试，延迟 ${(delay / 1000).toFixed(2)}s`);
                    await sleep(delay);
                    continue;
                }
                console.error(`[fail] status=${resp.status_code}: ${resp.text.slice(0, 300)}`);
                try { return JSON.parse(resp.text); } catch (e) { return null; }
            } catch (e) {
                lastErr = e;
                if (attempt < this.maxRetries && this._shouldRetry(null, e)) {
                    const delay = this._calcRetryDelay(attempt);
                    console.warn(`[retry] 异常: ${e.message}，第 ${attempt + 1} 次重试`);
                    await sleep(delay);
                    continue;
                }
                console.error(`[fail] 请求最终失败: ${e.message}`);
                return null;
            }
        }
        if (lastErr) console.error(`[retry] ${this.maxRetries} 次后仍失败: ${lastErr.message}`);
        else if (lastResp) console.error(`[retry] ${this.maxRetries} 次后仍失败，status=${lastResp.status_code}`);
        return null;
    }

    // ── 公开请求方法 ────────────────────────────────────────────────

    async get(url, { params, referer, headers, timeout } = {}) {
        return this._executeWithRetry(() => this._rawRequest('GET', url, { params, referer, headers, timeout }), url);
    }

    async post(url, { json, data, referer, headers, timeout } = {}) {
        const body = json != null ? json : (data != null ? data : '');
        return this._executeWithRetry(() => this._rawRequest('POST', url, { body, referer, headers, timeout }), url);
    }

    // ── 工具方法 ────────────────────────────────────────────────────

    generateRequestId() {
        return Date.now();
    }

    updateCookies(newCookies) {
        if (newCookies && typeof newCookies === 'object') {
            this.cookies = newCookies;
        } else {
            console.error('[cookies] 更新失败：不支持的数据类型');
        }
    }
}

module.exports = { BaseRequest, DEFAULT_USER_AGENT, sanitize };

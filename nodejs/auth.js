'use strict';
/**
 * 拼多多扫码登录 + cookies 持久化（Node.js 自包含版）
 * ====================================================
 * 基于 09_login_api.json，通过 3 个核心 HTTP 端点实现扫码登录。
 * 支持多店铺 cookies 文件持久化（cookies.json）。
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const { URL } = require('url');
const { generateAntiContent, DEFAULT_USER_AGENT } = require('./anti_content');

const BASE_URL = 'https://mms.pinduoduo.com';
const QRCODE_URL = `${BASE_URL}/janus/api/scan/login/qrcode`;
const SCAN_QUERY_URL = `${BASE_URL}/janus/api/scan/login/query`;
const USERINFO_URL = `${BASE_URL}/janus/api/new/userinfo`;
const AUTHTOKEN_URL = `${BASE_URL}/janus/api/subSystem/getAuthToken`;
const LOGIN_PAGE_URL = `${BASE_URL}/login/?redirectUrl=${BASE_URL}/`;

const POLL_INTERVAL = 2000;
const STATUS_WAITING = 1;
const STATUS_SCANNED = 2;
const STATUS_SUCCESS = 3;

const COOKIES_FILE = path.resolve(__dirname, 'cookies.json');

function buildFingerprint() {
    return {
        innerHeight: 752, innerWidth: 1179, devicePixelRatio: 1.5,
        availHeight: 1040, availWidth: 1920, height: 1080, width: 1920,
        colorDepth: 24, locationHref: LOGIN_PAGE_URL,
        clientWidth: 1179, clientHeight: 752, offsetWidth: 1179, offsetHeight: 752,
        scrollWidth: 1179, scrollHeight: 752,
        navigator: {
            appCodeName: 'Mozilla', appName: 'Netscape', hardwareConcurrency: 8,
            language: 'zh-CN', cookieEnabled: true, platform: 'Win32', ua: DEFAULT_USER_AGENT,
        },
    };
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

class PDDAuth {
    constructor(opts = {}) {
        this.cookiesFile = opts.cookiesFile || COOKIES_FILE;
        this._cookieJar = {};
        this._ticket = null;
        this._fingerprint = buildFingerprint();
    }

    // ── 底层请求（带 cookies 收集） ──────────────────────────────────

    _post(url, data) {
        return new Promise((resolve) => {
            let ac = '';
            try { ac = generateAntiContent(); } catch (e) { ac = ''; }
            const u = new URL(url);
            const headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'content-type': 'application/json;charset=UTF-8',
                'origin': BASE_URL,
                'referer': LOGIN_PAGE_URL,
                'user-agent': DEFAULT_USER_AGENT,
            };
            if (ac) headers['anti-content'] = ac;
            const cookieStr = Object.entries(this._cookieJar).map(([k, v]) => `${k}=${v}`).join('; ');
            if (cookieStr) headers['cookie'] = cookieStr;
            const payload = JSON.stringify(data);
            headers['content-length'] = Buffer.byteLength(payload);
            const req = https.request({
                method: 'POST', hostname: u.hostname, port: 443,
                path: u.pathname + u.search, headers, timeout: 15000,
            }, (res) => {
                let chunks = '';
                res.on('data', d => chunks += d);
                res.on('end', () => {
                    // 收集 Set-Cookie
                    const setCookies = res.headers['set-cookie'] || [];
                    for (const sc of setCookies) {
                        const pair = sc.split(';')[0];
                        const idx = pair.indexOf('=');
                        if (idx > 0) {
                            this._cookieJar[pair.slice(0, idx).trim()] = pair.slice(idx + 1).trim();
                        }
                    }
                    try { resolve(JSON.parse(chunks)); } catch (e) { resolve(null); }
                });
            });
            req.on('error', (e) => { console.error('[auth] 请求失败:', e.message); resolve(null); });
            req.on('timeout', () => { req.destroy(new Error('timeout')); });
            req.write(payload);
            req.end();
        });
    }

    // ── 扫码登录核心 ────────────────────────────────────────────────

    async getQrcode() {
        const result = await this._post(QRCODE_URL, { fingerprint: this._fingerprint });
        if (!result || !result.success) {
            console.error('[auth] 获取二维码失败:', (result || {}).errorMsg);
            return null;
        }
        const uri = (result.result || {}).uri;
        if (!uri) { console.error('[auth] 响应中未找到 uri'); return null; }
        if (uri.includes('data=')) {
            this._ticket = uri.split('data=')[1];
        } else {
            this._ticket = null;
        }
        console.info('[auth] 获取二维码成功:', uri);
        return uri;
    }

    async queryScanStatus(ticket) {
        const t = ticket || this._ticket;
        if (!t) return { status: 0, success: false, user_info: null, error_msg: '无 ticket' };
        const result = await this._post(SCAN_QUERY_URL, { data: t, fingerprint: this._fingerprint });
        if (!result || !result.success) {
            return { status: 0, success: false, user_info: null, error_msg: (result || {}).errorMsg || '请求失败' };
        }
        const res = result.result || {};
        return { status: res.status || 0, success: true, user_info: res.userInfoVO, error_msg: '' };
    }

    async waitForScan(timeout = 120, onStatus) {
        if (!this._ticket) { console.error('[auth] 无 ticket'); return null; }
        const deadline = Date.now() + timeout * 1000;
        let count = 0;
        console.info(`[auth] 开始轮询扫码状态（超时 ${timeout}s）...`);
        while (Date.now() < deadline) {
            count++;
            const result = await this.queryScanStatus();
            const status = result.status;
            if (onStatus) { try { onStatus(status, result); } catch (e) {} }
            if (status === STATUS_WAITING) {
                if (count === 1) console.info('[auth] 等待用户扫码...');
            } else if (status === STATUS_SCANNED) {
                console.info('[auth] 用户已扫码，等待手机确认...');
            } else if (status === STATUS_SUCCESS) {
                const ui = result.user_info || {};
                const cookies = Object.assign({}, this._cookieJar);
                console.info(`[auth] 登录成功! user_id=${ui.id}, mall_id=${ui.mallId}`);
                return { cookies, user_id: ui.id, mall_id: ui.mallId, username: ui.username || '' };
            }
            if (!result.success) { console.error('[auth] 轮询失败:', result.error_msg); return null; }
            await sleep(POLL_INTERVAL);
        }
        console.warn(`[auth] 扫码超时（${timeout}s），共轮询 ${count} 次`);
        return null;
    }

    async getAuthToken(cookies) {
        if (cookies) Object.assign(this._cookieJar, cookies);
        const result = await this._post(AUTHTOKEN_URL, {});
        if (result && result.success) {
            const token = (result.result || {}).token;
            if (token) { console.info('[auth] 获取子系统 Token 成功'); return token; }
        }
        console.warn('[auth] 获取 Token 失败');
        return null;
    }

    async login(timeout = 120, onStatus) {
        const uri = await this.getQrcode();
        if (!uri) return null;
        return this.waitForScan(timeout, onStatus);
    }

    // ── cookies 持久化（多店铺） ────────────────────────────────────

    saveCookies(mallId, cookies, userId, username) {
        const data = this._loadAll();
        data[String(mallId)] = {
            cookies, user_id: String(userId || ''), username: username || '',
            saved_at: new Date().toISOString(),
        };
        this._saveAll(data);
        console.info(`[auth] 已保存店铺 ${mallId} 的 cookies（共 ${Object.keys(cookies).length} 项）`);
    }

    loadCookies(mallId) {
        const data = this._loadAll();
        const entry = data[String(mallId)];
        return entry ? entry.cookies : null;
    }

    getMallInfo(mallId) {
        return this._loadAll()[String(mallId)] || null;
    }

    listMalls() {
        const data = this._loadAll();
        return Object.entries(data).map(([mid, info]) => ({
            mall_id: mid, user_id: info.user_id || '', username: info.username || '',
            saved_at: info.saved_at || '',
        }));
    }

    logout(mallId) {
        const data = this._loadAll();
        if (data[String(mallId)]) {
            delete data[String(mallId)];
            this._saveAll(data);
            console.info(`[auth] 已登出店铺 ${mallId}`);
            return true;
        }
        return false;
    }

    _loadAll() {
        if (!fs.existsSync(this.cookiesFile)) return {};
        try { return JSON.parse(fs.readFileSync(this.cookiesFile, 'utf-8')); }
        catch (e) { console.error('[auth] 读取 cookies.json 失败:', e.message); return {}; }
    }

    _saveAll(data) {
        try { fs.writeFileSync(this.cookiesFile, JSON.stringify(data, null, 2), 'utf-8'); }
        catch (e) { console.error('[auth] 写入 cookies.json 失败:', e.message); }
    }

    makeReloginCallback() {
        return async (mallId) => {
            if (!mallId) { console.error('[auth] 重新登录需要 mallId'); return null; }
            console.info(`[auth] 触发店铺 ${mallId} 重新登录...`);
            const result = await this.login(120);
            if (result) {
                this.saveCookies(mallId, result.cookies, result.user_id, result.username);
                return result.cookies;
            }
            return null;
        };
    }
}

module.exports = { PDDAuth };

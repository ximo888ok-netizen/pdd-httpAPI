'use strict';
/**
 * 拼多多 API 聚合 SDK 客户端（Node.js 版）
 * ============================================
 * 统一入口，聚合 6 大业务模块 + 扫码登录。
 * 支持多店铺：通过 mallId 区分，cookies 从 cookies.json 持久化加载。
 *
 * 使用示例:
 *   const { PDDClient } = require('./client');
 *   const client = new PDDClient({ mallId: '256393917' });
 *   const user = await client.authShop.getUserInfo();
 *   await client.customerService.sendText('uid', '你好');
 *
 *   // 扫码登录
 *   const client2 = new PDDClient();
 *   const res = await client2.login(120);
 */
const { PDDAuth } = require('./auth');
const { BaseRequest } = require('./base_request');
const { AuthShopAPI } = require('./apis/auth_shop');
const { CustomerServiceAPI } = require('./apis/customer_service');
const { DataCenterAPI } = require('./apis/data_center');
const { ReviewAPI } = require('./apis/review_management');
const { ActivityEnrollAPI } = require('./apis/activity_enroll');
const { ProductAPI } = require('./apis/product_management');

class PDDClient {
    constructor(opts = {}) {
        this.auth = new PDDAuth();
        this.mallId = opts.mallId || null;
        this.autoLogin = !!opts.autoLogin;
        this.maxRetries = opts.maxRetries != null ? opts.maxRetries : 3;
        this.minInterval = opts.minInterval != null ? opts.minInterval : 0.5;

        if (opts.cookies) {
            this.cookies = opts.cookies;
        } else if (this.mallId) {
            const loaded = this.auth.loadCookies(this.mallId);
            this.cookies = loaded || {};
            if (!loaded) console.warn(`[client] cookies.json 中未找到店铺 ${this.mallId}，请先登录`);
        } else {
            this.cookies = {};
        }

        this._reloginCb = null;
        if (this.autoLogin && this.mallId) {
            this._reloginCb = this.auth.makeReloginCallback();
        }

        this._authShop = null;
        this._customerService = null;
        this._dataCenter = null;
        this._review = null;
        this._activity = null;
        this._product = null;
    }

    async login(timeout = 120, onStatus) {
        const result = await this.auth.login(timeout, onStatus);
        if (!result) return null;
        const mallId = String(result.mall_id);
        this.auth.saveCookies(mallId, result.cookies, result.user_id, result.username);
        this.mallId = mallId;
        this.cookies = result.cookies;
        this._resetInstances();
        console.info(`[client] 登录成功并已绑定 mall_id=${mallId}`);
        return { mall_id: mallId, user_id: result.user_id, username: result.username, cookies: result.cookies };
    }

    _resetInstances() {
        this._authShop = null;
        this._customerService = null;
        this._dataCenter = null;
        this._review = null;
        this._activity = null;
        this._product = null;
    }

    _makeOpts() {
        const opts = { cookies: this.cookies, mallId: this.mallId,
                       maxRetries: this.maxRetries, minInterval: this.minInterval };
        if (this.autoLogin && this._reloginCb) {
            opts.autoRelogin = true;
            opts.reloginCallback = this._reloginCb;
        }
        return opts;
    }

    updateCookies(newCookies) {
        this.cookies = newCookies;
        this._resetInstances();
        if (this.mallId) this.auth.saveCookies(this.mallId, newCookies);
    }

    listMalls() { return this.auth.listMalls(); }

    logout() {
        if (this.mallId) return this.auth.logout(this.mallId);
        return false;
    }

    switchMall(mallId) {
        const loaded = this.auth.loadCookies(mallId);
        if (loaded) {
            this.mallId = mallId;
            this.cookies = loaded;
            this._resetInstances();
            console.info(`[client] 已切换到店铺 ${mallId}`);
            return true;
        }
        console.warn(`[client] 切换失败：未找到店铺 ${mallId}`);
        return false;
    }

    get authShop() {
        if (!this._authShop) this._authShop = new AuthShopAPI(this._makeOpts());
        return this._authShop;
    }
    get customerService() {
        if (!this._customerService) this._customerService = new CustomerServiceAPI(this._makeOpts());
        return this._customerService;
    }
    get dataCenter() {
        if (!this._dataCenter) this._dataCenter = new DataCenterAPI(this._makeOpts());
        return this._dataCenter;
    }
    get review() {
        if (!this._review) this._review = new ReviewAPI(this._makeOpts());
        return this._review;
    }
    get activity() {
        if (!this._activity) this._activity = new ActivityEnrollAPI(this._makeOpts());
        return this._activity;
    }
    get product() {
        if (!this._product) this._product = new ProductAPI(this._makeOpts());
        return this._product;
    }
}

module.exports = { PDDClient };

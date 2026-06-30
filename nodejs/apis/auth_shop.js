'use strict';
/** 认证与店铺信息 API（4 端点，来自 01_auth_and_shop.json） */
const { BaseRequest } = require('../base_request');
const BASE = 'https://mms.pinduoduo.com';

class AuthShopAPI extends BaseRequest {
    async getToken() {
        return this.post(`${BASE}/chats/getToken`, { data: '{}' });
    }
    async getUserInfo() {
        return this.post(`${BASE}/janus/api/new/userinfo`, { data: '{}' });
    }
    async getShopInfo() {
        return this.post(`${BASE}/earth/api/merchant/queryMerchantInfoByMallId`, { data: '{}' });
    }
    async setCsstatus(status) {
        return this.post(`${BASE}/plateau/chat/set_csstatus`, { json: { status } });
    }
}

module.exports = { AuthShopAPI };

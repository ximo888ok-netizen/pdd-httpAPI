'use strict';
/** 活动报名 API（6 端点，来自 05_activity_enroll.json） */
const { BaseRequest } = require('../base_request');
const BASE = 'https://mms.pinduoduo.com';
const ACT_REFERER = 'https://mms.pinduoduo.com/activity';

class ActivityEnrollAPI extends BaseRequest {
    async checkLogin() {
        return this.post(`${BASE}/janus/api/checkLogin`, { data: '', referer: ACT_REFERER });
    }
    async getActivityDetail(activityId) {
        return this.post(`${BASE}/leekmms/activity/query/detail`,
            { json: { activity_id: activityId, query_source: 1 }, referer: ACT_REFERER });
    }
    async getEligibleGoods(activityId, opts = {}) {
        const { goodsId = 0, goodsName = '', page = 1, pageSize = 10 } = opts;
        const data = { activity_id: activityId, goods_id: goodsId, goods_name: goodsName,
                       page_number: page, eligible: 1, page_size: pageSize };
        return this.post(`${BASE}/leekmms/activity/query/eligible/goods/listV2`, { json: data, referer: ACT_REFERER });
    }
    async getPriceRules(activityId, goodsIdList) {
        return this.post(`${BASE}/leekmms/activity/query/enroll/rule_v3`,
            { json: { activity_id: activityId, goods_id_list: goodsIdList }, referer: ACT_REFERER });
    }
    async getSuggestPrices(activityId, goodsIdList) {
        const data = { activity_id: activityId, goods_id_list: goodsIdList, source_type: 'PROMO-HomeModule' };
        return this.post(`${BASE}/leekmms/activity/query/enroll/rule_suggest_price`, { json: data, referer: ACT_REFERER });
    }
    async doEnroll(activityId, goodsVolist) {
        const url = `${BASE}/lakemms/enrollV2`;
        const body = { activity_id: activityId, goods_volist: goodsVolist };
        let result = await this.post(url, { json: body, referer: ACT_REFERER });
        if (!result) return null;
        const errorCode = result.error_code;
        if (errorCode === 30001) {
            console.info('[activity] 30001 建议价过期，刷新后重试...');
            const ids = goodsVolist.map(g => g.goods_id).filter(Boolean);
            if (ids.length) await this.getSuggestPrices(activityId, ids);
            result = await this.post(url, { json: body, referer: ACT_REFERER });
        } else if (errorCode === 2002690) {
            console.info('[activity] 2002690 库存超限，去库存后重试...');
            const stripped = goodsVolist.map(g => { const ng = Object.assign({}, g); delete ng.quantity; delete ng.sku_quantity; return ng; });
            result = await this.post(url, { json: { activity_id: activityId, goods_volist: stripped }, referer: ACT_REFERER });
        }
        return result;
    }
}

module.exports = { ActivityEnrollAPI };

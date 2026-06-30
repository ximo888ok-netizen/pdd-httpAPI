'use strict';
/** 数据中心 API（6 端点，来自 03_data_center.json） */
const { BaseRequest } = require('../base_request');
const BASE = 'https://mms.pinduoduo.com';
const HOME_REFERER = 'https://mms.pinduoduo.com/home';

class DataCenterAPI extends BaseRequest {
    async queryTradeList(queryType = 6, queryDate = '') {
        return this.post(`${BASE}/sydney/api/mallTrade/queryMallTradeList`,
            { json: { queryType, queryDate }, referer: HOME_REFERER });
    }
    async queryMallScore() {
        return this.post(`${BASE}/sydney/api/mallScore/queryMallScoreInfo`, { data: '{}', referer: HOME_REFERER });
    }
    async querySaleQuality(queryDate = '') {
        return this.post(`${BASE}/sydney/api/saleQuality/querySaleQualityDetailInfo`,
            { json: { queryDate }, referer: HOME_REFERER });
    }
    async queryNotPayOrder() {
        return this.post(`${BASE}/sydney/api/mallTrade/getMallNotPayOrderInfoV2`, { data: '{}', referer: HOME_REFERER });
    }
    async queryHomeOverview() {
        return this.post(`${BASE}/sydney/api/mallCoreData/homePageOverView`, { data: '{}', referer: HOME_REFERER });
    }
    async queryHomePromotionOverview() {
        return this.post(`${BASE}/sydney/api/mallCoreData/homePagePromotionOverView`, { data: '{}', referer: HOME_REFERER });
    }
}

module.exports = { DataCenterAPI };

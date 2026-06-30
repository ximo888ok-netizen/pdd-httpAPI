'use strict';
/** 评价管理 API（6 端点，来自 04_review_management.json） */
const { BaseRequest } = require('../base_request');
const BASE = 'https://mms.pinduoduo.com';
const REVIEW_REFERER = 'https://mms.pinduoduo.com/reviews.html';

class ReviewAPI extends BaseRequest {
    async getReviewsList(opts = {}) {
        const { pageNo = 1, pageSize = 10, startTime = null, endTime = null,
                orderSn = '', descScore = null } = opts;
        const data = { startTime, endTime, pageNo, pageSize, orderSn: orderSn || '', descScore };
        return this.post(`${BASE}/saturn/reviews/list`, { json: data, referer: REVIEW_REFERER });
    }
    async getReviewsTypeAgg(rangeType = 4) {
        return this.post(`${BASE}/saturn/reviews/type/agg`, { json: { rangeType }, referer: REVIEW_REFERER });
    }
    async getReviewsKeywordsAgg(opts = {}) {
        const { rangeType = 4, startTime = null, endTime = null } = opts;
        return this.post(`${BASE}/saturn/reviews/keywords/agg`,
            { json: { startTime, endTime, rangeType }, referer: REVIEW_REFERER });
    }
    async getReviewDetail(reviewId, goodsId) {
        return this.post(`${BASE}/saturn/reviews/detail/info`,
            { json: { reviewId, goodsId }, referer: REVIEW_REFERER });
    }
    async createReportedReview(reviewId, reportType = '8', pictureUrls = [], describes = '') {
        const data = { reviewId, reportType, pictureUrls, describes };
        return this.post(`${BASE}/saturn/reportedReview/edit/createReportedReview`,
            { json: data, referer: REVIEW_REFERER });
    }
    async queryReportedReviewNum() {
        return this.post(`${BASE}/saturn/reportedReview/query/queryTypesReportedReviewNum`,
            { data: '{}', referer: REVIEW_REFERER });
    }
}

module.exports = { ReviewAPI };

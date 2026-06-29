'use strict';
/**
 * 商品管理 API（15 端点，来自 06_product_management.json）
 * 含图片上传三步流程、AI 能力、上架/下架/删除（⚠️待抓包）
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const { URL } = require('url');
const { BaseRequest } = require('../base_request');
const { generateAntiContent, requiresAntiContent, DEFAULT_USER_AGENT } = require('../anti_content');

const BASE = 'https://mms.pinduoduo.com';
const IMAGE_UPLOAD_BASE = 'https://file.pinduoduo.com';
const CATEGORY_REFERER = 'https://mms.pinduoduo.com/goods/category';
const GOODS_ADD_REFERER = 'https://mms.pinduoduo.com/goods/goods_add/index';

class ProductAPI extends BaseRequest {
    // ── 商品列表与详情 ──────────────────────────────────────────────
    async getProductList(page = 1, pageSize = 20) {
        return this.post(`${BASE}/latitude/goods/recommendGoods`,
            { json: { page, page_size: pageSize }, referer: `${BASE}/goods/list` });
    }
    async getProductDetail(goodsId) {
        return this.post(`${BASE}/glide/v2/mms/query/commit/on_shop/detail`,
            { json: { goods_id: goodsId }, referer: GOODS_ADD_REFERER });
    }

    // ── 类目查询（GET） ────────────────────────────────────────────
    async searchCategories(keyword) {
        return this.get(`${BASE}/vodka/v2/mms/search/categories/v2`, { params: { keyword }, referer: CATEGORY_REFERER });
    }
    async getCategoryDetail(catId) {
        return this.get(`${BASE}/vodka/v2/mms/category/detail`, { params: { catId }, referer: CATEGORY_REFERER });
    }
    async getCategoryChildren(parentId) {
        return this.get(`${BASE}/vodka/v2/mms/categories`, { params: { parentId }, referer: CATEGORY_REFERER });
    }
    async getLevel1Categories() {
        return this.get(`${BASE}/vodka/v2/mms/cat1List`, { referer: CATEGORY_REFERER });
    }

    // ── 商品创建/编辑 ──────────────────────────────────────────────
    async createDraft(catId) {
        return this.post(`${BASE}/glide/v2/mms/edit/commit/create_new`,
            { json: { cat_id: catId }, referer: CATEGORY_REFERER });
    }
    async saveDraft(data) {
        const gcId = data.goods_commit_id || '';
        const gId = data.goods_id || '';
        const referer = `${GOODS_ADD_REFERER}?id=${gcId}&goods_id=${gId}`;
        return this.post(`${BASE}/glide/mms/goodsCommit/action/edit`, { json: data, referer });
    }
    async saveSpuKeyProperties(goodsCommitId, goodsId, keyProperties) {
        const data = { goods_commit_id: goodsCommitId, goods_id: goodsId, key_properties: keyProperties };
        const referer = `${GOODS_ADD_REFERER}?id=${goodsCommitId}&goods_id=${goodsId}`;
        return this.post(`${BASE}/glide/mms/goodsCommit/action/edit_spu_key_properties`, { json: data, referer });
    }
    async getDraftDetail(goodsCommitId) {
        return this.post(`${BASE}/glide/v2/mms/query/commit/detail`,
            { json: { goods_commit_id: goodsCommitId }, referer: GOODS_ADD_REFERER });
    }

    // ── 商品模板与规则 ──────────────────────────────────────────────
    async getPublishTemplate(catId, goodsCommitId, goodsId) {
        const data = { cat_id: catId };
        if (goodsCommitId != null) data.goods_commit_id = goodsCommitId;
        if (goodsId != null) data.goods_id = goodsId;
        return this.post(`${BASE}/draco-ms/mms/template/mall`, { json: data, referer: GOODS_ADD_REFERER });
    }
    async getPublishRules(catId) {
        return this.post(`${BASE}/glide/v2/mms/query/rules/limit/new`,
            { json: { cat_id: catId }, referer: GOODS_ADD_REFERER });
    }
    async getBrandList(catId, keyword = '') {
        const data = { cat_id: catId };
        if (keyword) data.keyword = keyword;
        return this.post(`${BASE}/draco-ms/mms/brand/audit/record`, { json: data, referer: GOODS_ADD_REFERER });
    }

    // ── 规格管理 ────────────────────────────────────────────────────
    async querySpecNames(catId) {
        return this.post(`${BASE}/glide/v2/mms/query/spec/name/list`,
            { json: { cat_id: catId }, referer: GOODS_ADD_REFERER });
    }
    async createSpecValue(parentId, name, catId) {
        return this.post(`${BASE}/glide/v2/mms/query/spec/by/name`,
            { json: { parent_id: parentId, name, cat_id: catId }, referer: GOODS_ADD_REFERER });
    }

    // ── 图片上传（三步流程） ───────────────────────────────────────
    async _getUploadSignature(bucketTag = 'mms-goods-image') {
        return this.post(`${BASE}/galerie/business/get_signature`,
            { json: { bucket_tag: bucketTag }, referer: GOODS_ADD_REFERER });
    }
    async _getUploadEndpoint(bucketTag = 'mms-goods-image') {
        return this.post(`${IMAGE_UPLOAD_BASE}/api/galerie/get_endpoint`,
            { json: { bucket_tag: bucketTag }, referer: GOODS_ADD_REFERER });
    }
    async uploadImage(filePath, bucketTag = 'mms-goods-image') {
        if (!fs.existsSync(filePath)) { console.error('[product] 图片不存在:', filePath); return null; }
        const sig = await this._getUploadSignature(bucketTag);
        if (!sig || !sig.success) { console.error('[product] 获取签名失败'); return null; }
        const endpoint = (await this._getUploadEndpoint(bucketTag));
        if (!endpoint || !endpoint.success) { console.error('[product] 获取上传地址失败'); return null; }
        const ep = (endpoint.result || {}).endpoint;
        if (!ep) { console.error('[product] endpoint 为空'); return null; }
        // 上传文件 multipart
        return this._uploadFile(`https://${ep}/v3/store_image`, filePath);
    }

    _uploadFile(uploadUrl, filePath) {
        return new Promise((resolve) => {
            const u = new URL(uploadUrl);
            const boundary = '----PDD' + Date.now();
            const fileName = path.basename(filePath);
            const fileBuf = fs.readFileSync(filePath);
            const parts = [
                `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${fileName}"\r\nContent-Type: application/octet-stream\r\n\r\n`,
                fileBuf,
                `\r\n--${boundary}--\r\n`,
            ];
            const payload = Buffer.concat(parts.map(p => Buffer.isBuffer(p) ? p : Buffer.from(p)));
            const headers = this._buildHeaders(uploadUrl, GOODS_ADD_REFERER);
            delete headers['content-type'];
            headers['content-type'] = `multipart/form-data; boundary=${boundary}`;
            headers['content-length'] = payload.length;
            const cookieStr = Object.entries(this.cookies).map(([k, v]) => `${k}=${v}`).join('; ');
            if (cookieStr) headers['cookie'] = cookieStr;
            const req = https.request({
                method: 'POST', hostname: u.hostname, port: 443,
                path: u.pathname + u.search, headers, timeout: 60000,
            }, (res) => {
                let chunks = '';
                res.on('data', d => chunks += d);
                res.on('end', () => {
                    try {
                        const data = JSON.parse(chunks);
                        if (data.success || data.url) {
                            resolve((data.result || {}).url || data.url);
                        } else { console.error('[product] 上传失败:', chunks.slice(0, 300)); resolve(null); }
                    } catch (e) { console.error('[product] 上传响应解析失败:', chunks.slice(0, 300)); resolve(null); }
                });
            });
            req.on('error', (e) => { console.error('[product] 上传异常:', e.message); resolve(null); });
            req.on('timeout', () => { req.destroy(new Error('timeout')); });
            req.write(payload);
            req.end();
        });
    }

    // ── 图片空间管理 ────────────────────────────────────────────────
    async listImageDirs(parentDirId = 0) {
        return this.post(`${BASE}/garner/mms/dir/dirListV2`,
            { json: { parent_dir_id: parentDirId }, referer: GOODS_ADD_REFERER });
    }
    async listImageFiles(dirId, page = 1, pageSize = 20) {
        return this.post(`${BASE}/garner/mms/file/list`,
            { json: { dir_id: dirId, page, page_size: pageSize }, referer: GOODS_ADD_REFERER });
    }
    async makeThumbnail(url, width = 0, height = 0, ifCut = false, dx = 0, dy = 0) {
        return this.post(`${BASE}/glide/v2/mms/image/thumbnail`,
            { json: { url, width, height, if_cut: ifCut, dx, dy }, referer: GOODS_ADD_REFERER });
    }

    // ── AI 能力 ─────────────────────────────────────────────────────
    async aiRecommendProperties(imageUrl, catId) {
        return this.post(`${BASE}/witcher/api/properties-recommender-by-img`,
            { json: { image_url: imageUrl, cat_id: catId }, referer: GOODS_ADD_REFERER });
    }
    async aiRecommendTitle(imageUrl, catName) {
        return this.post(`${BASE}/witcher/api/rec-goods-title`,
            { json: { image_url: imageUrl, cat_name: catName }, referer: GOODS_ADD_REFERER });
    }

    // ── 上架/下架/删除（⚠️ 端点待抓包确认） ──────────────────────────
    async setListingStatus(goodsIds, online = true) {
        const p = online ? '/japi/goods/listing' : '/japi/goods/offline';
        console.warn(`[product] setListingStatus 端点 ${p} 基于推测，待抓包确认`);
        return this.post(`${BASE}${p}`, { json: { goods_ids: goodsIds }, referer: `${BASE}/goods/list` });
    }
    async deleteProducts(goodsIds) {
        console.warn('[product] deleteProducts 端点基于推测，待抓包确认');
        return this.post(`${BASE}/japi/goods/delete`, { json: { goods_ids: goodsIds }, referer: `${BASE}/goods/list` });
    }
}

module.exports = { ProductAPI };

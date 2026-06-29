'use strict';
/** 客服消息 API（5 端点，来自 02_customer_service.json） */
const { BaseRequest } = require('../base_request');
const BASE = 'https://mms.pinduoduo.com';
const CHAT_REFERER = 'https://mms.pinduoduo.com/chat-merchant/index.html';

class CustomerServiceAPI extends BaseRequest {
    async sendText(toUid, content) {
        const data = {
            data: {
                cmd: 'send_message', request_id: this.generateRequestId(),
                message: {
                    to: { role: 'user', uid: toUid }, from: { role: 'mall_cs' },
                    content, msg_id: null, type: 0, is_aut: 0, manual_reply: 1,
                },
            },
            client: 'WEB',
        };
        return this.post(`${BASE}/plateau/chat/send_message`, { json: data, referer: CHAT_REFERER });
    }

    async sendImage(toUid, imageUrl) {
        const data = {
            data: {
                cmd: 'send_message', request_id: this.generateRequestId(),
                message: {
                    to: { role: 'user', uid: toUid }, from: { role: 'mall_cs' },
                    content: imageUrl, msg_id: null, chat_type: 'cs', type: 1, is_aut: 0, manual_reply: 1,
                }
            },
            client: 'WEB',
        };
        return this.post(`${BASE}/plateau/chat/send_message`, { json: data, referer: CHAT_REFERER });
    }

    async sendGoodsCard(toUid, goodsId, bizType = 2) {
        const data = { uid: toUid, goods_id: goodsId, biz_type: bizType };
        return this.post(`${BASE}/plateau/message/send/mallGoodsCard`, { json: data, referer: CHAT_REFERER });
    }

    async getAssignCsList() {
        return this.post(`${BASE}/latitude/assign/getAssignCsList`, { json: { wechatCheck: true }, referer: CHAT_REFERER });
    }

    async moveConversation(uid, csUid, remark = '无原因直接转移') {
        const data = {
            data: {
                cmd: 'move_conversation', request_id: this.generateRequestId(),
                conversation: { csid: csUid, uid, need_wx: false, remark }
            },
            client: 'WEB',
        };
        return this.post(`${BASE}/plateau/chat/move_conversation`, { json: data, referer: CHAT_REFERER });
    }
}

module.exports = { CustomerServiceAPI };

'use strict';
/**
 * 拼多多 Anti-Content 签名生成器（Node.js 版）
 * 直接复用项目根 anti_content.js 的实现。
 */
const path = require('path');
const parent = require(path.resolve(__dirname, '..', 'anti_content.js'));

module.exports = {
    generateAntiContent: parent.generateAntiContent,
    requiresAntiContent: parent.requiresAntiContent,
    DEFAULT_USER_AGENT: parent.DEFAULT_USER_AGENT,
    RES_JS_PATH: parent.RES_JS_PATH,
};

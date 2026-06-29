# -*- coding: utf-8 -*-
"""
拼多多 API 请求基类（自包含版）
==============================
不依赖项目内 logger/db_manager/登录模块，完全自包含。
提供：重试机制、域名节流、Anti-Content 自动注入、cookies 管理。
"""
import json
import time
import random
import logging
import threading
import requests
from typing import Dict, Any, Optional, Union, Callable
from urllib.parse import urlparse

from anti_content import DEFAULT_USER_AGENT, generate_anti_content, requires_anti_content

logger = logging.getLogger("pdd_api")


class BaseRequest:
    """
    API 请求基类，统一管理 requests 请求。

    功能：
    - 指数退避重试 + 随机抖动
    - 按域名请求频率控制（mms.pinduoduo.com = 0.8s，其他 = 0.5s）
    - Anti-Content 头自动注入（白名单端点）
    - 统一错误处理与日志（敏感字段脱敏）

    注意：本类不实现自动重新登录。会话过期时返回响应数据，
    由上层（auth.py / 调用方）决定是否重新登录。
    """

    SESSION_EXPIRED_ERROR_CODE = 43001
    RETRY_JITTER_MIN = 0.1
    RETRY_JITTER_MAX = 0.3

    _last_request_time: Dict[str, float] = {}
    _rate_lock = threading.Lock()
    _DOMAIN_INTERVALS = {"mms.pinduoduo.com": 0.8}
    _DEFAULT_MIN_INTERVAL = 0.5

    _SENSITIVE_KEYS = {'password', 'cookies', 'token', 'api_key',
                       'access_token', 'anti-content', 'anti_content'}

    def __init__(self, cookies: Optional[Dict] = None, mall_id: Optional[str] = None,
                 max_retries: int = 3, retry_delay: float = 1.0, retry_backoff: float = 2.0,
                 min_request_interval: float = 0.5, auto_relogin: bool = False,
                 relogin_callback: Optional[Callable] = None):
        self.cookies = cookies or {}
        self.mall_id = mall_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.min_request_interval = min_request_interval
        self.auto_relogin = auto_relogin
        self._relogin_callback = relogin_callback
        self._relogin_attempted = False

        self.default_headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://mms.pinduoduo.com',
            'user-agent': DEFAULT_USER_AGENT,
            'priority': 'u=1, i',
        }

    # ── 请求头构建 ──────────────────────────────────────────────────────

    def _build_headers(self, url: str = "", referer: Optional[str] = None,
                       extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """构建请求头，自动注入 anti-content（仅白名单端点）"""
        headers = self.default_headers.copy()
        if referer:
            headers['referer'] = referer
        else:
            headers['referer'] = 'https://mms.pinduoduo.com/'
        # anti-content 自动注入
        if url and requires_anti_content(url):
            try:
                ac = generate_anti_content()
                if ac:
                    headers['anti-content'] = ac
            except Exception as e:
                logger.warning("生成 anti-content 失败（端点 %s）: %s", url, e)
        if extra:
            headers.update(extra)
        return headers

    # ── 频率控制 ──────────────────────────────────────────────────────

    def _rate_limit(self, url: str) -> None:
        """按域名节流，避免高频触发风控"""
        if not self.min_request_interval or not url:
            return
        try:
            domain = urlparse(url).hostname or ""
        except Exception:
            return
        if not domain:
            return
        interval = self._DOMAIN_INTERVALS.get(domain, self.min_request_interval)
        if interval <= 0:
            return
        with self._rate_lock:
            now = time.time()
            last = self._last_request_time.get(domain, 0.0)
            wait = interval - (now - last)
            if wait > 0:
                logger.debug("频率控制: %s 等待 %.3fs", domain, wait)
                time.sleep(wait)
            self._last_request_time[domain] = time.time()

    # ── 重试机制 ──────────────────────────────────────────────────────

    def _should_retry(self, response: Optional[requests.Response] = None,
                      exception: Optional[Exception] = None) -> bool:
        if exception:
            if isinstance(exception, (requests.ConnectionError, requests.Timeout,
                                      requests.HTTPError, requests.TooManyRedirects)):
                return True
        if response:
            if response.status_code >= 500:
                return True
            if response.status_code in (429, 408, 502, 503, 504):
                return True
        return False

    def _calc_retry_delay(self, attempt: int) -> float:
        delay = self.retry_delay * (self.retry_backoff ** attempt)
        jitter = random.uniform(self.RETRY_JITTER_MIN, self.RETRY_JITTER_MAX) * delay
        return delay + jitter

    def _is_session_expired(self, data: Dict[str, Any]) -> bool:
        if not data:
            return False
        if (data.get('error_code') == self.SESSION_EXPIRED_ERROR_CODE and
                '会话已过期' in str(data.get('error_msg', ''))):
            return True
        return False

    def _execute_with_retry(self, request_func: Callable, expect_json: bool = True,
                            url: str = "") -> Optional[Dict[str, Any]]:
        last_exception = None
        last_response = None
        for attempt in range(self.max_retries + 1):
            try:
                if attempt == 0 and url:
                    self._rate_limit(url)
                response = request_func()
                if response and response.status_code == 200:
                    data = self._handle_response(response, expect_json)
                    # 会话过期处理
                    if (data and self._is_session_expired(data) and
                            not self._relogin_attempted and self.auto_relogin and
                            self._relogin_callback):
                        logger.info("检测到会话过期，尝试重新登录...")
                        self._relogin_attempted = True
                        new_cookies = self._relogin_callback(self.mall_id)
                        if new_cookies:
                            self.update_cookies(new_cookies)
                            continue
                    return data
                last_response = response
                if attempt < self.max_retries and self._should_retry(response=response):
                    delay = self._calc_retry_delay(attempt)
                    logger.warning("请求失败 status=%s，第 %d 次重试，延迟 %.2fs",
                                   response.status_code, attempt + 1, delay)
                    time.sleep(delay)
                    continue
                return self._handle_response(response, expect_json)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries and self._should_retry(exception=e):
                    delay = self._calc_retry_delay(attempt)
                    logger.warning("请求异常: %s，第 %d 次重试，延迟 %.2fs",
                                   e, attempt + 1, delay)
                    time.sleep(delay)
                    continue
                logger.error("请求最终失败: %s", e)
                return None
        if last_exception:
            logger.error("重试 %d 次后仍失败: %s", self.max_retries, last_exception)
        elif last_response:
            logger.error("重试 %d 次后仍失败，最后状态码: %s",
                         self.max_retries, last_response.status_code)
        return None

    # ── 响应处理 ──────────────────────────────────────────────────────

    def _handle_response(self, response: requests.Response,
                         expect_json: bool = True) -> Optional[Dict[str, Any]]:
        try:
            if response.status_code != 200:
                logger.error("请求失败 status=%s, body=%s",
                             response.status_code, response.text[:500])
                return None
            if expect_json:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.error("JSON 解析失败: %s", response.text[:500])
                    return None
            return {"text": response.text, "status_code": response.status_code}
        except Exception as e:
            logger.error("处理响应出错: %s", e)
            return None

    def _sanitize(self, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        result = {}
        for k, v in data.items():
            if k.lower() in self._SENSITIVE_KEYS or any(s in k.lower() for s in self._SENSITIVE_KEYS):
                result[k] = '***'
            elif isinstance(v, dict):
                result[k] = self._sanitize(v)
            elif isinstance(v, list):
                result[k] = [self._sanitize(i) if isinstance(i, dict) else i for i in v]
            else:
                result[k] = v
        return result

    def _log_request(self, method: str, url: str, **kwargs):
        logger.debug("%s %s", method, url)
        params = kwargs.get('data') or kwargs.get('json')
        if params:
            logger.debug("请求参数: %s", self._sanitize(params))

    # ── 公开请求方法 ──────────────────────────────────────────────────

    def get(self, url: str, params: Optional[Dict] = None,
            referer: Optional[str] = None, headers: Optional[Dict[str, str]] = None,
            timeout: int = 30, expect_json: bool = True, **kwargs) -> Optional[Dict[str, Any]]:
        merged = self._build_headers(url, referer, headers)
        self._log_request("GET", url, params=params)

        def _make():
            return requests.get(url, params=params, headers=merged,
                                cookies=self.cookies, timeout=timeout, **kwargs)

        return self._execute_with_retry(_make, expect_json=expect_json, url=url)

    def post(self, url: str, data: Optional[Union[Dict, str]] = None,
             json_data: Optional[Dict] = None, referer: Optional[str] = None,
             headers: Optional[Dict[str, str]] = None, timeout: int = 30,
             expect_json: bool = True, **kwargs) -> Optional[Dict[str, Any]]:
        merged = self._build_headers(url, referer, headers)
        self._log_request("POST", url, data=data, json=json_data)

        def _make():
            return requests.post(url, data=data, json=json_data, headers=merged,
                                 cookies=self.cookies, timeout=timeout, **kwargs)

        return self._execute_with_retry(_make, expect_json=expect_json, url=url)

    # ── 工具方法 ──────────────────────────────────────────────────────

    def generate_request_id(self) -> int:
        return int(time.time() * 1000)

    def update_cookies(self, new_cookies: Union[Dict, str]) -> None:
        if isinstance(new_cookies, str):
            try:
                self.cookies = json.loads(new_cookies)
            except json.JSONDecodeError:
                logger.error("更新 cookies 失败: JSON 解析错误")
        elif isinstance(new_cookies, dict):
            self.cookies = new_cookies
        else:
            logger.error("更新 cookies 失败: 不支持的数据类型")

    def set_default_header(self, key: str, value: str) -> None:
        self.default_headers[key] = value

    def set_retry_config(self, max_retries: int = None, retry_delay: float = None,
                         retry_backoff: float = None) -> None:
        if max_retries is not None:
            self.max_retries = max_retries
        if retry_delay is not None:
            self.retry_delay = retry_delay
        if retry_backoff is not None:
            self.retry_backoff = retry_backoff

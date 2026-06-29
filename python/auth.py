# -*- coding: utf-8 -*-
"""
拼多多扫码登录 + cookies 持久化（自包含版）
============================================
基于 09_login_api.json，通过 3 个核心 HTTP 端点实现扫码登录。
支持多店铺 cookies 文件持久化（cookies.json）。
"""
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Callable

import requests

from anti_content import DEFAULT_USER_AGENT, generate_anti_content

logger = logging.getLogger("pdd_auth")

BASE_URL = "https://mms.pinduoduo.com"
QRCODE_URL = f"{BASE_URL}/janus/api/scan/login/qrcode"
SCAN_QUERY_URL = f"{BASE_URL}/janus/api/scan/login/query"
USERINFO_URL = f"{BASE_URL}/janus/api/new/userinfo"
AUTHTOKEN_URL = f"{BASE_URL}/janus/api/subSystem/getAuthToken"
LOGIN_PAGE_URL = f"{BASE_URL}/login/?redirectUrl={BASE_URL}/"

POLL_INTERVAL = 2.0
STATUS_WAITING = 1
STATUS_SCANNED = 2
STATUS_SUCCESS = 3

COOKIES_FILE = Path(__file__).resolve().parent / "cookies.json"


class PDDAuth:
    """拼多多扫码登录 + 多店铺 cookies 管理"""

    def __init__(self, cookies_file: Optional[Path] = None):
        self.cookies_file = cookies_file or COOKIES_FILE
        self.session: requests.Session = requests.Session()
        self.session.headers.update({
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/json;charset=UTF-8",
            "origin": BASE_URL,
            "referer": LOGIN_PAGE_URL,
            "user-agent": DEFAULT_USER_AGENT,
        })
        self._ticket: Optional[str] = None
        self._fingerprint: Dict[str, Any] = self._build_fingerprint()

    # ── 指纹构建 ──────────────────────────────────────────────────────

    @staticmethod
    def _build_fingerprint() -> Dict[str, Any]:
        """构建固定浏览器指纹（来自 09_login_api.json 示例值）"""
        return {
            "innerHeight": 752,
            "innerWidth": 1179,
            "devicePixelRatio": 1.5,
            "availHeight": 1040,
            "availWidth": 1920,
            "height": 1080,
            "width": 1920,
            "colorDepth": 24,
            "locationHref": LOGIN_PAGE_URL,
            "clientWidth": 1179,
            "clientHeight": 752,
            "offsetWidth": 1179,
            "offsetHeight": 752,
            "scrollWidth": 1179,
            "scrollHeight": 752,
            "navigator": {
                "appCodeName": "Mozilla",
                "appName": "Netscape",
                "hardwareConcurrency": 8,
                "language": "zh-CN",
                "cookieEnabled": True,
                "platform": "Win32",
                "ua": DEFAULT_USER_AGENT,
            },
        }

    # ── 请求封装 ──────────────────────────────────────────────────────

    def _post(self, url: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            anti_content = generate_anti_content()
        except Exception:
            anti_content = ""
        headers = {"anti-content": anti_content} if anti_content else {}
        try:
            resp = self.session.post(url, json=data, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("HTTP %s: %s", resp.status_code, url)
            return None
        except requests.RequestException as e:
            logger.error("请求失败 %s: %s", url, e)
            return None

    # ── 扫码登录核心 ──────────────────────────────────────────────────

    def get_qrcode(self) -> Optional[str]:
        """获取登录二维码 URL"""
        data = {"fingerprint": self._fingerprint}
        result = self._post(QRCODE_URL, data)
        if not result or not result.get("success"):
            err = (result or {}).get("errorMsg", "请求失败")
            logger.error("获取二维码失败: %s", err)
            return None
        uri = result.get("result", {}).get("uri")
        if not uri:
            logger.error("响应中未找到二维码 uri")
            return None
        if "data=" in uri:
            self._ticket = uri.split("data=", 1)[1]
        else:
            self._ticket = None
            logger.warning("无法从二维码 URL 提取 ticket: %s", uri)
        logger.info("获取二维码成功: %s", uri)
        return uri

    def query_scan_status(self, ticket: Optional[str] = None) -> Dict[str, Any]:
        """查询单次扫码状态"""
        t = ticket or self._ticket
        if not t:
            return {"status": 0, "success": False, "user_info": None,
                    "error_msg": "无 ticket，请先调用 get_qrcode()"}
        data = {"data": t, "fingerprint": self._fingerprint}
        result = self._post(SCAN_QUERY_URL, data)
        if not result or not result.get("success"):
            err = (result or {}).get("errorMsg", "请求失败")
            return {"status": 0, "success": False, "user_info": None, "error_msg": err}
        res = result.get("result", {})
        return {
            "status": res.get("status", 0),
            "success": True,
            "user_info": res.get("userInfoVO"),
            "error_msg": "",
        }

    def wait_for_scan(self, timeout: int = 120,
                      on_status: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """阻塞等待扫码登录完成"""
        if not self._ticket:
            logger.error("无 ticket，请先调用 get_qrcode()")
            return None
        deadline = time.time() + timeout
        poll_count = 0
        logger.info("开始轮询扫码状态（超时 %ss）...", timeout)
        while time.time() < deadline:
            poll_count += 1
            result = self.query_scan_status()
            status = result["status"]
            if on_status:
                try:
                    on_status(status, result)
                except Exception:
                    pass
            if status == STATUS_WAITING:
                if poll_count == 1:
                    logger.info("等待用户扫码...")
            elif status == STATUS_SCANNED:
                logger.info("用户已扫码，等待手机确认...")
            elif status == STATUS_SUCCESS:
                user_info = result.get("user_info") or {}
                cookies = dict(self.session.cookies)
                logger.info("扫码登录成功! user_id=%s, mall_id=%s",
                            user_info.get("id"), user_info.get("mallId"))
                return {
                    "cookies": cookies,
                    "user_id": user_info.get("id"),
                    "mall_id": user_info.get("mallId"),
                    "username": user_info.get("username", ""),
                }
            if not result["success"]:
                logger.error("轮询失败: %s", result["error_msg"])
                return None
            time.sleep(POLL_INTERVAL)
        logger.warning("扫码超时（%ss），共轮询 %d 次", timeout, poll_count)
        return None

    def get_auth_token(self, cookies: Optional[Dict] = None) -> Optional[str]:
        """获取子系统认证 Token"""
        if cookies:
            self.session.cookies.update(cookies)
        result = self._post(AUTHTOKEN_URL, {})
        if result and result.get("success"):
            token = result.get("result", {}).get("token")
            if token:
                logger.info("获取子系统认证 Token 成功")
                return token
        logger.warning("获取认证 Token 失败: %s", result)
        return None

    def login(self, timeout: int = 120,
              on_status: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
        """一键扫码登录（get_qrcode + wait_for_scan）"""
        qrcode_url = self.get_qrcode()
        if not qrcode_url:
            return None
        return self.wait_for_scan(timeout=timeout, on_status=on_status)

    # ── cookies 持久化（多店铺） ──────────────────────────────────────

    def save_cookies(self, mall_id: str, cookies: Dict, user_id: Any = None,
                     username: str = "") -> None:
        """保存某店铺 cookies 到文件"""
        data = self._load_all()
        data[str(mall_id)] = {
            "cookies": cookies,
            "user_id": str(user_id) if user_id is not None else "",
            "username": username,
            "saved_at": datetime.now().isoformat(),
        }
        self._save_all(data)
        logger.info("已保存店铺 %s 的 cookies（共 %d 项）", mall_id, len(cookies))

    def load_cookies(self, mall_id: str) -> Optional[Dict]:
        """读取某店铺 cookies"""
        data = self._load_all()
        entry = data.get(str(mall_id))
        if entry:
            return entry.get("cookies")
        return None

    def get_mall_info(self, mall_id: str) -> Optional[Dict[str, Any]]:
        """读取某店铺完整信息（cookies + user_id + username）"""
        data = self._load_all()
        return data.get(str(mall_id))

    def list_malls(self) -> list:
        """列出已登录的所有店铺"""
        data = self._load_all()
        result = []
        for mid, info in data.items():
            result.append({
                "mall_id": mid,
                "user_id": info.get("user_id", ""),
                "username": info.get("username", ""),
                "saved_at": info.get("saved_at", ""),
            })
        return result

    def logout(self, mall_id: str) -> bool:
        """删除某店铺 cookies"""
        data = self._load_all()
        if str(mall_id) in data:
            del data[str(mall_id)]
            self._save_all(data)
            logger.info("已登出店铺 %s", mall_id)
            return True
        return False

    def _load_all(self) -> Dict[str, Any]:
        if not self.cookies_file.exists():
            return {}
        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("读取 cookies.json 失败: %s", e)
            return {}

    def _save_all(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.cookies_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("写入 cookies.json 失败: %s", e)

    # ── 重新登录回调（供 BaseRequest 使用） ────────────────────────────

    def make_relogin_callback(self) -> Callable:
        """返回一个重新登录回调函数，供 BaseRequest.auto_relogin 使用"""
        def _relogin(mall_id: Optional[str]) -> Optional[Dict]:
            if not mall_id:
                logger.error("重新登录需要 mall_id")
                return None
            logger.info("触发店铺 %s 重新登录...", mall_id)
            result = self.login(timeout=120)
            if result:
                self.save_cookies(mall_id, result["cookies"],
                                  result.get("user_id"), result.get("username", ""))
                return result["cookies"]
            return None
        return _relogin


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    auth = PDDAuth()

    def _status(status, info):
        labels = {1: "等待扫码", 2: "已扫码，等待确认", 3: "登录成功"}
        print(f"  [状态] {labels.get(status, f'未知({status})')}")

    res = auth.login(timeout=120, on_status=_status)
    if res:
        print(f"\n登录成功! mall_id={res['mall_id']}, username={res['username']}")
        auth.save_cookies(str(res["mall_id"]), res["cookies"],
                          res.get("user_id"), res.get("username", ""))
        print(f"cookies 已保存到 {auth.cookies_file}")
    else:
        print("\n登录失败或超时")

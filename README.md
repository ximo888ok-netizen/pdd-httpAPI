# PDD商家后台 HTTP API 封装

> **免责声明**：本项目仅供学习交流和技术研究使用，不得用于任何商业用途。使用者需自行承担因不当使用产生的一切法律责任，与本项目作者无关。

把 `pdd-httpAPI/` 里 9 份 JSON 文档记录的端点做成了可调用的代码。Python 和 Node.js 各一套，每套都有 SDK 和 Web 服务两种用法。登录走扫码，cookies 存文件，支持多店铺。签名头自动生成。

---

## 目录结构

```
pdd-httpAPI/
├── 00_index.json ~ 09_login_api.json   # 接口文档（原有，未改动）
├── anti_content.js                      # 签名生成器（原有，未改动）
│
├── python/
│   ├── anti_content.py                  # 签名生成，execjs 调外部 res.js
│   ├── base_request.py                  # 请求基类，带重试/节流/签名注入
│   ├── auth.py                          # 扫码登录 + cookies 读写
│   ├── client.py                        # PDDClient，聚合下面 6 个模块
│   ├── server.py                        # FastAPI 服务
│   ├── apis/
│   │   ├── auth_shop.py                 # 认证与店铺（4 端点）
│   │   ├── customer_service.py          # 客服消息（5 端点）
│   │   ├── data_center.py               # 数据中心（6 端点）
│   │   ├── review_management.py         # 评价管理（6 端点）
│   │   ├── activity_enroll.py           # 活动报名（6 端点）
│   │   └── product_management.py        # 商品管理（15 端点）
│   └── requirements.txt
│
└── nodejs/
    ├── anti_content.js                  # 复用上层 anti_content.js
    ├── base_request.js                  # 请求基类，零依赖，用内置 https
    ├── auth.js
    ├── client.js
    ├── server.js                        # 原生 http 服务
    ├── apis/                            # 6 个模块，跟 Python 侧一一对应
    └── package.json
```

两套代码互相独立，不依赖项目里其他模块。唯一的外部引用是 `Anti-Content-pdd/res.js`（签名算法，只读）。

---

## 用法

### Python

```bash
cd pdd-httpAPI/python
pip install -r requirements.txt
```

SDK：

```python
from client import PDDClient

# 用已登录的店铺（从 cookies.json 读 cookies）
client = PDDClient(mall_id="256393917")

# 或者扫码登录
client = PDDClient()
client.login(timeout=120)

# 之后直接调
client.auth_shop.get_user_info()
client.customer_service.send_text(to_uid="xxx", content="你好")
client.product.create_draft(cat_id=24027)
```

Web 服务：

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Swagger 在 http://localhost:8000/docs 。

### Node.js

```bash
cd pdd-httpAPI/nodejs
# 不用装依赖
```

SDK：

```javascript
const { PDDClient } = require('./client');

const client = new PDDClient({ mallId: '256393917' });
// 或扫码登录
const client = new PDDClient();
await client.login(120);

await client.authShop.getUserInfo();
await client.customerService.sendText('uid', '你好');
await client.product.createDraft(24027);
```

Web 服务：

```bash
node server.js   # 监听 8001
```

Python 用 8000，Node.js 用 8001，两边路由路径一致。

---

## 登录

走的是 `09_login_api.json` 里的扫码登录，3 个端点：

1. `POST /janus/api/scan/login/qrcode` — 拿二维码 URL，请求体带个固定的 fingerprint
2. `POST /janus/api/scan/login/query` — 轮询状态，2 秒一次，status 1=等扫码 / 2=已扫 / 3=成功
3. `POST /janus/api/subSystem/getAuthToken` — 拿子系统 token

`client.login()` 把这三步串起来。登录成功后 cookies 写进 `cookies.json`，下次直接传 `mall_id` 就行，不用再扫。

Web 服务登录：

```bash
# 拿二维码
curl -X POST http://localhost:8000/login/qrcode
# 返回 {"qrcode_url": "https://w.url.cn/s/...", "ticket": "..."}

# 等扫码完成（阻塞到扫完或超时）
curl -X POST http://localhost:8000/login/wait -H "Content-Type: application/json" -d '{"timeout":120}'
```

---

## 多店铺

`cookies.json` 按 `mall_id` 存，Python 和 Node.js 读写同一个文件：

```json
{
  "256393917": {
    "cookies": {"api_uid": "...", "rckk": "..."},
    "user_id": "178496330",
    "username": "pdd25639391748",
    "saved_at": "2026-06-29T12:00:00"
  }
}
```

SDK 里：

```python
client.list_malls()              # 看有哪些店铺
client.switch_mall("256393917")  # 切换
client.logout()                  # 登出当前
```

Web 服务：

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/malls` | 列出所有店铺 |
| DELETE | `/malls/{mall_id}` | 登出某店铺 |

---

## 端点清单

业务接口都在 `/api/{mall_id}/` 下。下面列路由和对应的 SDK 方法，请求体字段看 [08_all_request_fields.json](08_all_request_fields.json)。

### 认证与店铺（01）
| 方法 | 路径 | SDK |
|------|------|-----|
| POST | `/auth/token` | `auth_shop.get_token()` |
| POST | `/auth/userinfo` | `auth_shop.get_user_info()` |
| POST | `/auth/shop` | `auth_shop.get_shop_info()` |
| POST | `/auth/csstatus` | `auth_shop.set_csstatus(status)` |

### 客服消息（02）
| 方法 | 路径 | SDK |
|------|------|-----|
| POST | `/customer/send_text` | `customer_service.send_text(to_uid, content)` |
| POST | `/customer/send_image` | `customer_service.send_image(to_uid, image_url)` |
| POST | `/customer/send_goods_card` | `customer_service.send_goods_card(to_uid, goods_id)` |
| GET | `/customer/assign_cs_list` | `customer_service.get_assign_cs_list()` |
| POST | `/customer/move_conversation` | `customer_service.move_conversation(uid, cs_uid)` |

### 数据中心（03）
| 方法 | 路径 | SDK |
|------|------|-----|
| POST | `/data/trade_list` | `data_center.query_trade_list()` |
| POST | `/data/mall_score` | `data_center.query_mall_score()` |
| POST | `/data/sale_quality` | `data_center.query_sale_quality()` |
| POST | `/data/not_pay_order` | `data_center.query_not_pay_order()` |
| POST | `/data/home_overview` | `data_center.query_home_overview()` |
| POST | `/data/home_promotion_overview` | `data_center.query_home_promotion_overview()` |

### 评价管理（04）
| 方法 | 路径 | SDK |
|------|------|-----|
| POST | `/reviews/list` | `review.get_reviews_list()` |
| POST | `/reviews/type_agg` | `review.get_reviews_type_agg()` |
| POST | `/reviews/keywords_agg` | `review.get_reviews_keywords_agg()` |
| POST | `/reviews/detail` | `review.get_review_detail()` |
| POST | `/reviews/report` | `review.create_reported_review()` |
| GET | `/reviews/reported_num` | `review.query_reported_review_num()` |

### 活动报名（05）
| 方法 | 路径 | SDK |
|------|------|-----|
| POST | `/activity/check_login` | `activity.check_login()` |
| POST | `/activity/detail` | `activity.get_activity_detail()` |
| POST | `/activity/eligible_goods` | `activity.get_eligible_goods()` |
| POST | `/activity/price_rules` | `activity.get_price_rules()` |
| POST | `/activity/suggest_prices` | `activity.get_suggest_prices()` |
| POST | `/activity/enroll` | `activity.do_enroll()` |

### 商品管理（06）
| 方法 | 路径 | SDK |
|------|------|-----|
| POST | `/product/list` | `product.get_product_list()` |
| POST | `/product/detail` | `product.get_product_detail()` |
| GET | `/product/categories/search` | `product.search_categories()` |
| GET | `/product/categories/detail` | `product.get_category_detail()` |
| GET | `/product/categories/children` | `product.get_category_children()` |
| GET | `/product/categories/level1` | `product.get_level1_categories()` |
| POST | `/product/draft/create` | `product.create_draft()` |
| POST | `/product/draft/save` | `product.save_draft()` |
| POST | `/product/draft/spu_properties` | `product.save_spu_key_properties()` |
| POST | `/product/draft/detail` | `product.get_draft_detail()` |
| POST | `/product/template` | `product.get_publish_template()` |
| POST | `/product/rules` | `product.get_publish_rules()` |
| POST | `/product/brands` | `product.get_brand_list()` |
| POST | `/product/spec_names` | `product.query_spec_names()` |
| POST | `/product/spec_value` | `product.create_spec_value()` |
| POST | `/product/image/thumbnail` | `product.make_thumbnail()` |
| POST | `/product/image/dirs` | `product.list_image_dirs()` |
| POST | `/product/image/files` | `product.list_image_files()` |
| POST | `/product/ai/properties` | `product.ai_recommend_properties()` |
| POST | `/product/ai/title` | `product.ai_recommend_title()` |
| POST | `/product/listing` | `product.set_listing_status()` |
| POST | `/product/delete` | `product.delete_products()` |

`save_draft` 的 100+ 字段看 [docs/07_product_create_required_fields.json](docs/07_product_create_required_fields.json)。

`/product/listing`、`/product/delete` 这三个上下架删除的端点是按推测实现的（文档里标了待抓包），用之前最好自己抓包确认一下。

---

## 响应格式

业务接口统一返回：

```json
{"success": true, "data": {...}, "error": null}
```

失败：

```json
{"success": false, "data": null, "error": "错误描述"}
```

店铺没登录就调业务接口，返回 401：

```json
{"detail": "店铺 999 未登录或 cookies 已失效，请先登录"}
```

---

## 实现说明

**签名**：Python 用 `execjs` 编译 `res.js`，Node.js 用内置 `vm` 模块跑。580KB 的 JS 只编译一次，后面复用。不是所有请求都要签名，`requires_anti_content()` 按白名单判断，命中的才塞 `anti-content` 头。

**请求基类**做了这几件事：
- 重试：指数退避 + 随机抖动，默认 3 次
- 节流：`mms.pinduoduo.com` 0.8s 一次，其他域名 0.5s，类级别共享
- 会话过期：响应里 `error_code=43001` 且带"会话已过期"时，如果开了 `auto_login` 就自动重新登录再重试
- 日志脱敏：cookies、token、anti-content 这些字段打日志时替换成 `***`

**依赖**：Python 那几个包在 `requirements.txt` 里（requests、fastapi、uvicorn、PyExecJS、pydantic）。Node.js 零依赖，只用内置模块。

**没做的**：Playwright 账号密码登录（只有扫码）、WebSocket 收消息（只有 HTTP 发）、数据库（只存文件）。`pdd-httpAPI/` 外面的文件一个没动。

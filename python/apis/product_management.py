# -*- coding: utf-8 -*-
"""商品管理 API（15 端点，来自 06_product_management.json）"""
import os
import logging
from typing import Optional, Dict, Any, List
from base_request import BaseRequest

BASE = "https://mms.pinduoduo.com"
IMAGE_UPLOAD_BASE = "https://file.pinduoduo.com"
CATEGORY_REFERER = "https://mms.pinduoduo.com/goods/category"
GOODS_ADD_REFERER = "https://mms.pinduoduo.com/goods/goods_add/index"

logger = logging.getLogger("pdd_product")


class ProductAPI(BaseRequest):
    """商品管理接口（含创建/上架全流程）"""

    # ── 商品列表与详情 ──────────────────────────────────────────────────

    def get_product_list(self, page: int = 1, page_size: int = 20) -> Optional[Dict[str, Any]]:
        """获取店铺商品列表 → POST /latitude/goods/recommendGoods"""
        url = f"{BASE}/latitude/goods/recommendGoods"
        return self.post(url, json_data={"page": page, "page_size": page_size},
                         referer=f"{BASE}/goods/list")

    def get_product_detail(self, goods_id: int) -> Optional[Dict[str, Any]]:
        """获取已上架商品详情 → POST /glide/v2/mms/query/commit/on_shop/detail"""
        url = f"{BASE}/glide/v2/mms/query/commit/on_shop/detail"
        return self.post(url, json_data={"goods_id": goods_id}, referer=GOODS_ADD_REFERER)

    # ── 类目查询（GET） ────────────────────────────────────────────────

    def search_categories(self, keyword: str) -> Optional[Dict[str, Any]]:
        """搜索商品类目 → GET /vodka/v2/mms/search/categories/v2?keyword="""
        url = f"{BASE}/vodka/v2/mms/search/categories/v2"
        return self.get(url, params={"keyword": keyword}, referer=CATEGORY_REFERER)

    def get_category_detail(self, cat_id: int) -> Optional[Dict[str, Any]]:
        """获取类目层级路径 → GET /vodka/v2/mms/category/detail?catId="""
        url = f"{BASE}/vodka/v2/mms/category/detail"
        return self.get(url, params={"catId": cat_id}, referer=CATEGORY_REFERER)

    def get_category_children(self, parent_id: int) -> Optional[Dict[str, Any]]:
        """获取子类目列表 → GET /vodka/v2/mms/categories?parentId="""
        url = f"{BASE}/vodka/v2/mms/categories"
        return self.get(url, params={"parentId": parent_id}, referer=CATEGORY_REFERER)

    def get_level1_categories(self) -> Optional[Dict[str, Any]]:
        """获取所有一级类目 → GET /vodka/v2/mms/cat1List"""
        url = f"{BASE}/vodka/v2/mms/cat1List"
        return self.get(url, referer=CATEGORY_REFERER)

    # ── 商品创建/编辑 ──────────────────────────────────────────────────

    def create_draft(self, cat_id: int) -> Optional[Dict[str, Any]]:
        """创建商品草稿 → POST /glide/v2/mms/edit/commit/create_new

        Args:
            cat_id: 四级叶子类目 ID

        Returns:
            含 goods_commit_id（草稿ID）和 goods_id
        """
        url = f"{BASE}/glide/v2/mms/edit/commit/create_new"
        return self.post(url, json_data={"cat_id": cat_id}, referer=CATEGORY_REFERER)

    def save_draft(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """保存商品草稿（100+ 字段）→ POST /glide/mms/goodsCommit/action/edit

        Args:
            data: 完整商品数据，参考 07_product_create_required_fields.json。
                  应含 goods_commit_id, goods_id, cat_id 等。
        """
        url = f"{BASE}/glide/mms/goodsCommit/action/edit"
        goods_commit_id = data.get("goods_commit_id", "")
        goods_id = data.get("goods_id", "")
        referer = f"{GOODS_ADD_REFERER}?id={goods_commit_id}&goods_id={goods_id}"
        return self.post(url, json_data=data, referer=referer)

    def save_spu_key_properties(self, goods_commit_id: str, goods_id: int,
                                key_properties: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """保存 SPU 关键属性 → POST /glide/mms/goodsCommit/action/edit_spu_key_properties

        Args:
            goods_commit_id: 草稿 ID
            goods_id: 商品 ID
            key_properties: SPU 属性列表，每项含 {key, value, id}
        """
        url = f"{BASE}/glide/mms/goodsCommit/action/edit_spu_key_properties"
        data = {
            "goods_commit_id": goods_commit_id,
            "goods_id": goods_id,
            "key_properties": key_properties,
        }
        referer = f"{GOODS_ADD_REFERER}?id={goods_commit_id}&goods_id={goods_id}"
        return self.post(url, json_data=data, referer=referer)

    def get_draft_detail(self, goods_commit_id: str) -> Optional[Dict[str, Any]]:
        """获取草稿详情 → POST /glide/v2/mms/query/commit/detail"""
        url = f"{BASE}/glide/v2/mms/query/commit/detail"
        return self.post(url, json_data={"goods_commit_id": goods_commit_id},
                         referer=GOODS_ADD_REFERER)

    # ── 商品模板与规则 ────────────────────────────────────────────────

    def get_publish_template(self, cat_id: int, goods_commit_id: Optional[str] = None,
                             goods_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """获取发布模板 → POST /draco-ms/mms/template/mall"""
        url = f"{BASE}/draco-ms/mms/template/mall"
        data = {"cat_id": cat_id}
        if goods_commit_id is not None:
            data["goods_commit_id"] = goods_commit_id
        if goods_id is not None:
            data["goods_id"] = goods_id
        return self.post(url, json_data=data, referer=GOODS_ADD_REFERER)

    def get_publish_rules(self, cat_id: int) -> Optional[Dict[str, Any]]:
        """获取发布规则限制 → POST /glide/v2/mms/query/rules/limit/new"""
        url = f"{BASE}/glide/v2/mms/query/rules/limit/new"
        return self.post(url, json_data={"cat_id": cat_id}, referer=GOODS_ADD_REFERER)

    def get_brand_list(self, cat_id: int, keyword: str = "") -> Optional[Dict[str, Any]]:
        """获取已审核品牌列表 → POST /draco-ms/mms/brand/audit/record"""
        url = f"{BASE}/draco-ms/mms/brand/audit/record"
        data = {"cat_id": cat_id}
        if keyword:
            data["keyword"] = keyword
        return self.post(url, json_data=data, referer=GOODS_ADD_REFERER)

    # ── 规格管理 ──────────────────────────────────────────────────────

    def query_spec_names(self, cat_id: int) -> Optional[Dict[str, Any]]:
        """获取规格类型列表 → POST /glide/v2/mms/query/spec/name/list"""
        url = f"{BASE}/glide/v2/mms/query/spec/name/list"
        return self.post(url, json_data={"cat_id": cat_id}, referer=GOODS_ADD_REFERER)

    def create_spec_value(self, parent_id: int, name: str,
                          cat_id: int) -> Optional[Dict[str, Any]]:
        """按名称查询/创建规格值 → POST /glide/v2/mms/query/spec/by/name

        Args:
            parent_id: 规格类型 ID
            name: 规格值名称
            cat_id: 类目 ID
        """
        url = f"{BASE}/glide/v2/mms/query/spec/by/name"
        data = {"parent_id": parent_id, "name": name, "cat_id": cat_id}
        return self.post(url, json_data=data, referer=GOODS_ADD_REFERER)

    # ── 图片上传（三步流程） ───────────────────────────────────────────

    def _get_upload_signature(self, bucket_tag: str = "mms-goods-image") -> Optional[Dict[str, Any]]:
        """获取上传签名 → POST /galerie/business/get_signature"""
        url = f"{BASE}/galerie/business/get_signature"
        return self.post(url, json_data={"bucket_tag": bucket_tag}, referer=GOODS_ADD_REFERER)

    def _get_upload_endpoint(self, bucket_tag: str = "mms-goods-image") -> Optional[Dict[str, Any]]:
        """获取上传服务器地址 → POST file.pinduoduo.com/api/galerie/get_endpoint"""
        url = f"{IMAGE_UPLOAD_BASE}/api/galerie/get_endpoint"
        return self.post(url, json_data={"bucket_tag": bucket_tag}, referer=GOODS_ADD_REFERER)

    def upload_image(self, file_path: str,
                     bucket_tag: str = "mms-goods-image") -> Optional[str]:
        """上传图片到拼多多图床（三步流程合并）

        Args:
            file_path: 本地图片文件路径
            bucket_tag: bucket 标签

        Returns:
            图片 URL（pfs.pinduoduo.com），失败返回 None
        """
        if not os.path.exists(file_path):
            logger.error("图片文件不存在: %s", file_path)
            return None
        # 步骤1：获取签名
        sig = self._get_upload_signature(bucket_tag)
        if not sig or not sig.get("success"):
            logger.error("获取上传签名失败: %s", sig)
            return None
        signature = sig.get("result", {}).get("signature")
        # 步骤2：获取上传地址
        ep = self._get_upload_endpoint(bucket_tag)
        if not ep or not ep.get("success"):
            logger.error("获取上传地址失败: %s", ep)
            return None
        endpoint = ep.get("result", {}).get("endpoint")
        if not endpoint:
            logger.error("上传 endpoint 为空")
            return None
        # 步骤3：上传文件（multipart/form-data）
        upload_url = f"https://{endpoint}/v3/store_image"
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            headers = self._build_headers(upload_url, referer=GOODS_ADD_REFERER)
            headers.pop("content-type", None)
            import requests as _req
            try:
                resp = _req.post(upload_url, files=files, headers=headers,
                                 cookies=self.cookies, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") or "url" in data:
                        return data.get("result", {}).get("url") or data.get("url")
                logger.error("上传图片失败 status=%s: %s", resp.status_code, resp.text[:300])
            except Exception as e:
                logger.error("上传图片异常: %s", e)
        return None

    # ── 图片空间管理 ──────────────────────────────────────────────────

    def list_image_dirs(self, parent_dir_id: int = 0) -> Optional[Dict[str, Any]]:
        """列出图片空间目录 → POST /garner/mms/dir/dirListV2"""
        url = f"{BASE}/garner/mms/dir/dirListV2"
        return self.post(url, json_data={"parent_dir_id": parent_dir_id},
                         referer=GOODS_ADD_REFERER)

    def list_image_files(self, dir_id: int, page: int = 1,
                         page_size: int = 20) -> Optional[Dict[str, Any]]:
        """列出目录下图片文件 → POST /garner/mms/file/list"""
        url = f"{BASE}/garner/mms/file/list"
        data = {"dir_id": dir_id, "page": page, "page_size": page_size}
        return self.post(url, json_data=data, referer=GOODS_ADD_REFERER)

    def make_thumbnail(self, url: str, width: int = 0, height: int = 0,
                       if_cut: bool = False, dx: int = 0,
                       dy: int = 0) -> Optional[Dict[str, Any]]:
        """生成图片缩略图/裁剪 → POST /glide/v2/mms/image/thumbnail"""
        api_url = f"{BASE}/glide/v2/mms/image/thumbnail"
        data = {
            "url": url,
            "width": width,
            "height": height,
            "if_cut": if_cut,
            "dx": dx,
            "dy": dy,
        }
        return self.post(api_url, json_data=data, referer=GOODS_ADD_REFERER)

    # ── AI 能力 ───────────────────────────────────────────────────────

    def ai_recommend_properties(self, image_url: str,
                                cat_id: int) -> Optional[Dict[str, Any]]:
        """AI 推荐商品属性 → POST /witcher/api/properties-recommender-by-img"""
        url = f"{BASE}/witcher/api/properties-recommender-by-img"
        return self.post(url, json_data={"image_url": image_url, "cat_id": cat_id},
                         referer=GOODS_ADD_REFERER)

    def ai_recommend_title(self, image_url: str, cat_name: str) -> Optional[Dict[str, Any]]:
        """AI 推荐商品标题 → POST /witcher/api/rec-goods-title"""
        url = f"{BASE}/witcher/api/rec-goods-title"
        return self.post(url, json_data={"image_url": image_url, "cat_name": cat_name},
                         referer=GOODS_ADD_REFERER)

    # ── 上架/下架/删除（⚠️ 端点待抓包确认） ────────────────────────────

    def set_listing_status(self, goods_ids: List[int], online: bool = True) -> Optional[Dict[str, Any]]:
        """上架/下架商品

        Args:
            goods_ids: 商品 ID 列表
            online: True=上架, False=下架

        Note:
            端点基于推测（06 文档标注⚠️待抓包确认）：
            - 上架: POST /japi/goods/listing
            - 下架: POST /japi/goods/offline
        """
        path = "/japi/goods/listing" if online else "/japi/goods/offline"
        url = f"{BASE}{path}"
        logger.warning("set_listing_status 端点 %s 基于推测，待抓包确认", path)
        return self.post(url, json_data={"goods_ids": goods_ids}, referer=f"{BASE}/goods/list")

    def delete_products(self, goods_ids: List[int]) -> Optional[Dict[str, Any]]:
        """删除商品

        Note:
            端点基于推测（06 文档标注⚠️待抓包确认）: POST /japi/goods/delete
        """
        url = f"{BASE}/japi/goods/delete"
        logger.warning("delete_products 端点基于推测，待抓包确认")
        return self.post(url, json_data={"goods_ids": goods_ids}, referer=f"{BASE}/goods/list")

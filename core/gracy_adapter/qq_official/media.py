"""富媒体上传 — 图片/语音等资源上传

两个入口分别处理单聊和群聊的上传。
"""

import base64
import logging
import os
from typing import Optional

_logger = logging.getLogger("Gracy.QQOfficial.media")


class MediaMixin:
    """富媒体上传 Mixin — 依赖 AuthMixin 的 token 和 api_base"""

    async def upload_rich_media(
        self,
        openid: str,
        file_type: int,
        file_path: str = "",
        url: str = "",
    ) -> Optional[str]:
        """上传单聊富媒体资源"""
        return await self._upload_media(
            endpoint=f"{self._api_base}/v2/users/{openid}/files",
            file_type=file_type,
            file_path=file_path,
            url=url,
            log_prefix="",
        )

    async def upload_rich_media_group(
        self,
        group_openid: str,
        file_type: int,
        file_path: str = "",
        url: str = "",
    ) -> Optional[str]:
        """上传群聊富媒体资源"""
        return await self._upload_media(
            endpoint=f"{self._api_base}/v2/groups/{group_openid}/files",
            file_type=file_type,
            file_path=file_path,
            url=url,
            log_prefix="群聊",
        )

    async def _upload_media(
        self,
        endpoint: str,
        file_type: int,
        file_path: str = "",
        url: str = "",
        log_prefix: str = "",
    ) -> Optional[str]:
        token = await self.get_access_token()
        if not token:
            _logger.error(f"[QQOfficial] 上传{log_prefix}富媒体失败: 无有效 Token")
            return None

        headers = {"Authorization": f"QQBot {token}"}
        payload = {"file_type": file_type, "srv_send_msg": False}

        if file_path:
            if not os.path.exists(file_path):
                _logger.error(f"[QQOfficial] {log_prefix}文件不存在: {file_path}")
                return None
            try:
                with open(file_path, "rb") as f:
                    payload["file_data"] = base64.b64encode(f.read()).decode("utf-8")
                headers["Content-Type"] = "application/json"
                _logger.info(f"[QQOfficial] 正在上传{log_prefix}本地文件: {file_path}")
            except Exception as e:
                _logger.error(f"[QQOfficial] 读取{log_prefix}文件失败: {e}")
                return None
        elif url:
            payload["url"] = url
            headers["Content-Type"] = "application/json"
        else:
            _logger.error(f"[QQOfficial] 上传失败: 未提供 file_path 或 url")
            return None

        try:
            session = await self._get_session()
            async with session.post(endpoint, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _logger.info(f"[QQOfficial] {log_prefix}富媒体上传成功")
                    return data.get("file_info")
                error_body = await resp.text()
                _logger.error(f"[QQOfficial] {log_prefix}富媒体上传失败: {resp.status} {error_body}")
                return None
        except Exception as e:
            _logger.error(f"[QQOfficial] {log_prefix}富媒体上传异常: {e}")
            return None

import requests
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger("Gracy")


def _ws_fallback(action: str, params: dict = None) -> Optional[dict]:
    """WS 降级：HTTP API 不可用时走 WS 通道"""
    try:
        from core.gracy_adapter.send import gracy_call_api
        return gracy_call_api(action, params or {})
    except Exception:
        return None


class NapcatAPI:
    def __init__(self, napcat_http_url: str):
        self.napcat_http_url = napcat_http_url.rstrip('/')
        self._ws_fallback_enabled = True  # HTTP 失败自动走 WS
    
    def get_login_info(self) -> Optional[Dict]:
        """获取登录账号信息"""
        try:
            url = f"{self.napcat_http_url}/get_login_info"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("retcode") == 0:
                    return data.get("data")
        except Exception as e:
            logger.debug(f"HTTP 获取登录信息失败（将尝试 WS）: {e}")
        
        # WS 降级
        if self._ws_fallback_enabled:
            return _ws_fallback("get_login_info")
        return None
    
    def get_friend_list(self) -> Optional[list]:
        """获取好友列表"""
        try:
            url = f"{self.napcat_http_url}/get_friend_list"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("retcode") == 0:
                    return data.get("data", [])
        except Exception as e:
            logger.debug(f"HTTP 获取好友列表失败（将尝试 WS）: {e}")
        
        # WS 降级
        if self._ws_fallback_enabled:
            return _ws_fallback("get_friend_list")
        return None
    
    def get_group_list(self) -> Optional[list]:
        """获取群列表"""
        try:
            url = f"{self.napcat_http_url}/get_group_list"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("retcode") == 0:
                    return data.get("data", [])
        except Exception as e:
            logger.debug(f"HTTP 获取群列表失败（将尝试 WS）: {e}")
        
        # WS 降级
        if self._ws_fallback_enabled:
            return _ws_fallback("get_group_list")
        return None
    
    def get_version_info(self) -> Optional[Dict]:
        """获取版本信息"""
        try:
            url = f"{self.napcat_http_url}/get_version_info"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("retcode") == 0:
                    return data.get("data")
        except Exception as e:
            logger.debug(f"HTTP 获取版本信息失败（将尝试 WS）: {e}")
        
        # WS 降级
        if self._ws_fallback_enabled:
            return _ws_fallback("get_version_info")
        return None
    
    def get_robot_info(self) -> Dict:
        """获取机器人完整信息"""
        result = {
            "qq": "未知",
            "nickname": "未知",
            "avatar_url": None,
            "friend_count": 0,
            "group_count": 0,
            "napcat_version": "未知"
        }
        
        # 获取登录信息
        login_info = self.get_login_info()
        if login_info:
            result["qq"] = str(login_info.get("user_id", "未知"))
            result["nickname"] = login_info.get("nickname", "未知")
        
        # 获取好友数量
        friend_list = self.get_friend_list()
        if friend_list:
            result["friend_count"] = len(friend_list)
        
        # 获取群数量
        group_list = self.get_group_list()
        if group_list:
            result["group_count"] = len(group_list)
        
        # 获取版本信息
        version_info = self.get_version_info()
        if version_info:
            result["napcat_version"] = version_info.get("app_name", "未知") + " " + version_info.get("app_version", "")
        
        # 生成头像URL
        if result["qq"] != "未知":
            result["avatar_url"] = f"https://q1.qlogo.cn/g?b=qq&nk={result['qq']}&s=640"
        
        return result
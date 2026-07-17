from typing import Dict, Optional

from graci import get_logger; logger = get_logger("SysInfo.napcat")


class NapcatAPI:
    def __init__(self, napcat_http_url: str = ""):
        pass

    async def _call(self, action: str, params: dict = None) -> Optional[dict]:
        from graci import gracy_call_api
        return await gracy_call_api(action, params or {})
    
    async def get_login_info(self) -> Optional[Dict]:
        return await self._call("get_login_info")
    
    async def get_friend_list(self) -> Optional[list]:
        return await self._call("get_friend_list")
    
    async def get_group_list(self) -> Optional[list]:
        return await self._call("get_group_list")
    
    async def get_version_info(self) -> Optional[Dict]:
        return await self._call("get_version_info")
    
    async def get_robot_info(self) -> Dict:
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
        login_info = await self.get_login_info()
        if login_info:
            result["qq"] = str(login_info.get("user_id", "未知"))
            result["nickname"] = login_info.get("nickname", "未知")
        
        # 获取好友数量
        friend_list = await self.get_friend_list()
        if friend_list:
            result["friend_count"] = len(friend_list)
        
        # 获取群数量
        group_list = await self.get_group_list()
        if group_list:
            result["group_count"] = len(group_list)
        
        # 获取版本信息
        version_info = await self.get_version_info()
        if version_info:
            result["napcat_version"] = version_info.get("app_name", "未知") + " " + version_info.get("app_version", "")
        
        # 生成头像URL
        if result["qq"] != "未知":
            result["avatar_url"] = f"https://q1.qlogo.cn/g?b=qq&nk={result['qq']}&s=640"
        
        return result

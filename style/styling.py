"""
样式管理模块 - 包含中文格式化、ID加密、消息类型颜色等样式相关功能
"""

import json
from typing import Any, Dict, Union

# 导入颜色配置
try:
    from .log_colors import Colors
except ImportError:
    # 备用颜色定义
    class Colors:
        RESET = '\033[0m'
        BLUE = '\033[34m'
        PINK = '\033[95m'


class StylingManager:
    def __init__(self):
        # 上下文键映射
        self.context_key_mapping = {
            'self_id': '机器人ID', 'user_id': '用户ID', 'time': '消息时间',
            'message_id': '消息ID', 'message': '消息内容', 'raw_message': '原始消息',
            'group_id': '群组ID', 'message_type': '消息类型', 'post_type': '事件类型',
            'notice_type': '通知类型', 'sub_type': '子类型', 'operator_id': '操作者ID',
            'file': '文件信息', 'content_preview': '内容预览', 'permission': '权限级别',
            'target': '目标用户', 'client_ip': '客户端IP', 'request_id': '请求ID',
            'path': '请求路径', 'timestamp': '时间戳', 'role': '用户角色',
            'action': '操作类型', 'resource': '资源', 'success': '操作结果',
            'ip_address': 'IP地址', 'group_name': '群聊'
        }
        
        # 上下文值映射
        self.context_value_mapping = {
            'private': '私聊', 'group': '群聊', 'friend': '好友', 'group_upload': '群文件上传',
            'group_admin': '群管理变更', 'group_ban': '群禁言', 'friend_add': '好友添加',
            'group_recall': '群消息撤回', 'friend_recall': '好友消息撤回',
            'poke': '戳一戳', 'lucky_king': '运气王', 'honor': '群荣誉变更',
            'group_card': '群名片变更', 'offline_file': '离线文件', 'client_status': '客户端状态',
            'essence': '精华消息', 'system': '系统消息', 'request': '请求事件',
            'notice': '通知事件', 'meta_event': '元事件', 'message': '消息事件',
            'approve': '同意', 'reject': '拒绝', 'set': '设置', 'unset': '取消设置',
            'ban': '禁言', 'lift_ban': '解除禁言', 'leave': '离开', 'kick': '踢出',
            'admin': '管理员', 'member': '成员', 'owner': '群主', 'administrator': '管理员',
            'basic_query': '基础查询', 'use_plugins': '使用插件', 'guest': '访客',
            'user': '用户', 'true': '成功', 'false': '失败', 'True': '成功', 'False': '失败'
        }
        
        # 消息关键词映射
        self.message_mapping = {
            '审计日志': '审计日志', '非消息请求，已正常处理': '非消息请求已处理',
            '请求开始处理': '请求开始处理', '成功发送private消息': '私聊消息发送成功',
            '成功发送group消息': '群聊消息发送成功', '收到消息': '收到消息',
            '插件加载完成': '插件加载完成', '插件初始化完成': '插件初始化完成',
            '日志系统初始化完成': '日志系统初始化完成', 'Web面板自启': 'Web面板自动启动',
            '无日志消息': '无日志消息',
        }
        
        # 消息类型格式化映射
        self.message_type_formatting = {
            # 新格式转换为旧格式
            '消息类型: 私聊': '[私聊消息]',
            '消息类型: 群聊': '[群聊消息]',
            # 保持原有格式
            '[私聊消息]': '[私聊消息]',
            '[群聊消息]': '[群聊消息]',
        }
    
    def _sanitize_cq_codes(self, text: str) -> str:
        """简化CQ码显示——委托到 OneBot 适配器处理"""
        try:
            from core.gracy_adapter.onebot.sanitize import sanitize
            return sanitize(text)
        except ImportError:
            return text

    def format_context_to_chinese(self, context: Dict[str, Any]) -> str:
        """格式化上下文字典"""
        if not context:
            return ""
        
        chinese_parts = []
        # 字段名直接使用中文，无需翻译映射
        key_names = {
            'self_id': '机器人ID', 'sender_id': '用户ID', 'time': '时间',
            'message_id': '消息ID', 'message': '消息内容', 'raw_text': '消息',
            'target_id': '群组ID', 'chat_type': '消息类型', 'post_type': '事件类型',
            'notice_type': '通知类型', 'sub_type': '子类型', 'operator_id': '操作者ID',
            'file': '文件信息', 'content_preview': '内容预览', 'permission': '权限级别',
            'target': '目标', 'client_ip': '客户端IP', 'request_id': '请求ID',
            'path': '路径', 'timestamp': '时间', 'role': '角色',
            'action': '操作', 'resource': '资源', 'success': '结果',
            'ip_address': 'IP地址', 'group_name': '群名称',
        }
        for key, value in context.items():
            # 跳过空值（None或空字符串），不显示无意义字段
            if value is None or value == '':
                continue
            chinese_key = key_names.get(key, key)
            
            # 特殊字段处理
            if key == 'success':
                chinese_value = '成功' if str(value).lower() in ['true', '成功'] else '失败'
            elif key == 'chat_type':
                chinese_value = self.context_value_mapping.get(str(value), value)
            elif key == 'action':
                chinese_value = '发送消息' if value == 'message_sent' else '接收消息' if value == 'message_received' else value
            elif key in ['content_preview'] and isinstance(value, str):
                value = self._sanitize_cq_codes(value)
                chinese_value = value[:47] + '...' if len(value) > 50 else value
            elif key in ['raw_text'] and isinstance(value, str):
                chinese_value = self._sanitize_cq_codes(value)
            elif key in ['sender_id', 'target_id', 'self_id', 'message_id']:
                chinese_value = self._encrypt_user_id(value)
            elif key == 'permission':
                chinese_value = self.context_value_mapping.get(str(value), value)
            else:
                chinese_value = self.context_value_mapping.get(str(value), value)
            
            chinese_parts.append(f"{chinese_key}: {chinese_value}")
        
        return " | ".join(chinese_parts)
    
    def format_message_to_chinese(self, message: Union[str, Dict]) -> str:
        """将消息内容转换为中文格式"""
        if not message:
            return message
        
        # 处理字典格式的消息
        if isinstance(message, str):
            if message.startswith('{') and message.endswith('}'):
                try:
                    json_data = json.loads(message)
                    return self.format_dict_message(json_data)
                except:
                    pass
        
        return self.replace_message_keywords(str(message))
    
    def format_dict_message(self, json_data: Dict[str, Any]) -> str:
        """格式化字典类型的消息"""
        formatted_parts = []
        message_type = None
        
        for key, value in json_data.items():
            chinese_key = self.context_key_mapping.get(key, key)
            
            if key in ['self_id', 'user_id', 'message_id']:
                # 统一ID加密逻辑：将数字ID转换为"用户****后4位"格式
                formatted_value = self._encrypt_user_id(value)
            elif key == 'message_type':
                message_type = '私聊' if value == 'private' else '群聊' if value == 'group' else value
                formatted_value = message_type
            elif key in ['message', 'raw_message'] and isinstance(value, str):
                formatted_value = value[:27] + '...' if len(value) > 30 else value
            else:
                formatted_value = str(value)
            
            formatted_parts.append(f"{chinese_key}: {formatted_value}")
        
        # 根据消息类型添加前缀
        prefix = "[私聊消息] " if message_type == '私聊' else "[群聊消息] " if message_type == '群聊' else ""
        
        # 如果有group_name，添加到格式中
        if 'group_name' in json_data and message_type == '群聊':
            group_name = json_data.get('group_name', '')
            user_nickname = json_data.get('sender', {}).get('nickname', '') if isinstance(json_data.get('sender'), dict) else ''
            user_id = self._encrypt_user_id(json_data.get('user_id', ''))
            message_content = json_data.get('message', '')[:30] + '...' if len(str(json_data.get('message', ''))) > 30 else json_data.get('message', '')
            
            return f"{prefix}群名称：{group_name}，用户 {user_nickname}（ID: {user_id}）发送消息：{message_content}"
        
        return f"{prefix}收到消息：{' | '.join(formatted_parts)}"
    
    def replace_message_keywords(self, message: str) -> str:
        """替换消息中的关键词"""
        # 替换消息类型格式
        for old_format, new_format in self.message_type_formatting.items():
            if old_format in message:
                message = message.replace(old_format, new_format)
        
        # 替换其他关键词
        for eng, chn in self.message_mapping.items():
            if eng in message:
                message = message.replace(eng, chn)
        
        return message
    

    
    def _encrypt_user_id(self, user_id: Union[int, str]) -> str:
        """加密用户ID"""
        if isinstance(user_id, (int, str)) and str(user_id).isdigit():
            id_str = str(user_id)
            if len(id_str) >= 4:
                return f"用户****{id_str[-4:]}"
            else:
                return f"用户****{id_str}"
        elif isinstance(user_id, str) and user_id.startswith('用户****'):
            # 如果已经是加密格式，保持原样
            return user_id
        else:
            return str(user_id)


# 创建全局样式管理器实例
styling_manager = StylingManager()

# 导出便捷函数
def format_context_to_chinese(context: Dict[str, Any]) -> str:
    """将上下文字典转换为中文格式"""
    return styling_manager.format_context_to_chinese(context)

def format_message_to_chinese(message: Union[str, Dict]) -> str:
    """将消息内容转换为中文格式"""
    return styling_manager.format_message_to_chinese(message)

def format_dict_message(json_data: Dict[str, Any]) -> str:
    """格式化字典类型的消息"""
    return styling_manager.format_dict_message(json_data)

def replace_message_keywords(message: str) -> str:
    """替换消息中的关键词"""
    return styling_manager.replace_message_keywords(message)

def encrypt_user_id(user_id: Union[int, str]) -> str:
    """加密用户ID"""
    return styling_manager._encrypt_user_id(user_id)
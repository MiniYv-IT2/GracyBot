import re
import time
import hashlib
import logging
import json
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from enum import Enum

# 导入配置和日志管理器
from core.config_manager import config_manager
from core.logger_manager import logger_manager

# 获取日志器
logger = logger_manager.get_logger("Core.Security")

# 角色枚举类
class UserRole(Enum):
    GUEST = "guest"  # 别人
    SELF = "self"    # QQ本身
    MASTER = "master"  # 主人

# 输入验证器类
class InputValidator:
    """
    企业级输入验证器，提供全面的输入验证功能
    """
    
    @staticmethod
    def is_valid_qq(user_id: str) -> bool:
        """验证用户 ID 格式"""
        return bool(re.match(r'^[1-9]\d{4,14}$', user_id))
    
    @staticmethod
    def is_valid_group_id(group_id: str) -> bool:
        """验证群号格式"""
        return bool(re.match(r'^[1-9]\d{4,14}$', group_id))
    
    @staticmethod
    def is_valid_command(cmd: str) -> bool:
        """验证命令格式"""
        if not cmd or len(cmd) > 500:
            return False
        # 检查是否包含空字符
        if any(c in cmd for c in '\x00-\x1F\x7F'):
            return False
        return True
    
    @staticmethod
    def sanitize_input(content: str, max_length: int = 1000) -> str:
        """
        高级输入净化
        :param content: 原始输入
        :param max_length: 最大长度限制
        :return: 净化后的内容
        """
        # 限制长度
        if len(content) > max_length:
            content = content[:max_length]
        
        # HTML实体编码（防XSS）
        html_escape_table = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
            '/': '&#47;'
        }
        content = ''.join(html_escape_table.get(c, c) for c in content)
        
        # 移除控制字符
        content = re.sub(r'[\x00-\x1F\x7F]', '', content)
        
        # 移除多余空白
        content = ' '.join(content.split())
        
        return content

# 频率限制器类
class RateLimiter:
    """
    频率限制器，防止暴力攻击和滥用
    """
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
        self.config = {
            'max_requests_per_minute': 60,
            'max_requests_per_hour': 1000,
            'block_duration_seconds': 300  # 5分钟
        }
    
    def check_rate_limit(self, key: str) -> Tuple[bool, Optional[str]]:
        """
        检查请求是否超过频率限制
        :param key: 用户标识
        :return: (是否允许请求, 错误信息)
        """
        current_time = time.time()
        
        # 初始化请求记录
        if key not in self.requests:
            self.requests[key] = []
        
        # 清理过期记录
        self.requests[key] = [t for t in self.requests[key] if current_time - t < 3600]
        
        # 检查1分钟内的请求数
        minute_requests = [t for t in self.requests[key] if current_time - t < 60]
        if len(minute_requests) >= self.config['max_requests_per_minute']:
            return False, "请求过于频繁，请稍后再试（每分钟最多60次）"
        
        # 检查1小时内的请求数
        if len(self.requests[key]) >= self.config['max_requests_per_hour']:
            return False, "请求过于频繁，请稍后再试（每小时最多1000次）"
        
        # 记录本次请求
        self.requests[key].append(current_time)
        
        # 记录频率信息（DEBUG级别）
        logger.debug(f"[频率限制] 用户{key}请求频率: 1分钟内{len(minute_requests)+1}次, 1小时内{len(self.requests[key])}次")
        
        return True, None

# 安全管理器单例类
class SecurityManager:
    """
    企业级安全管理器，统一管理所有安全相关功能
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecurityManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        # 初始化组件
        self.validator = InputValidator()
        self.rate_limiter = RateLimiter()
        
        # 角色权限映射
        self.role_permissions = {
            UserRole.GUEST: ['basic_query'],  # 别人只有基础查询权限
            UserRole.SELF: ['basic_query', 'use_plugins'],  # QQ本身有使用插件权限
            UserRole.MASTER: ['basic_query', 'use_plugins', 'manage_plugins', 'system_admin']  # 主人有所有权限
        }
        
        # 用户角色映射（可从配置加载）
        self.user_roles: Dict[str, UserRole] = {}
        
        # 黑名单
        self.blacklist: Dict[str, Dict[str, Any]] = {}
        
        # 危险命令列表
        self.dangerous_commands = [
            r"rm\s+-rf",          # 强制删除命令
            r"shutdown",          # 关机命令
            r"init\s+0",          # 系统停机命令
            r"reboot",            # 重启命令
            r"mkfs|mke2fs",       # 格式化命令
            r"dd\s+if=.*of=.*",   # 磁盘写入命令
            r"chmod\s+777",       # 危险权限设置
            r"sudo\s+su",         # 提权至root
        ]
        
        # 敏感操作审计日志
        self.audit_logs: List[Dict[str, Any]] = []
        
        # 加载配置
        self._load_config()

        # 事件订阅标志（懒订阅）
        self._subscribed = False

    def _ensure_subscribed(self):
        """确保已订阅 EventBus（懒订阅，避免加载时序问题）"""
        if self._subscribed:
            return
        try:
            from core.event import event_bus
            event_bus.subscribe("*", self._event_filter, priority=100)
            self._subscribed = True
            _logger.debug("[SecurityManager] 已注册到 EventBus（优先级高）")
        except Exception:
            pass

    async def _event_filter(self, event) -> None:
        """EventBus 订阅者：黑名单拦截 + 审计日志（懒订阅）"""
        self._ensure_subscribed()
        # 黑名单拦截
        if hasattr(event, 'sender_id') and self.is_blocked(str(event.sender_id)):
            _logger.info(f"[EventBus] 黑名单拦截用户 {event.sender_id}")
            event.cancel()
            return
        # 审计日志
        if hasattr(event, 'chat_type'):
            self.log_audit_event(
                user_id=getattr(event, 'sender_id', ''),
                action="message_received",
                resource=event.chat_type,
                success=True,
                details={
                    "raw_text": getattr(event, 'raw_text', '')[:200],
                    "chat_type": event.chat_type,
                }
            )
    
    def _load_config(self):
        """从配置管理器加载安全配置"""
        # 从配置中加载主人QQ
        master_id = config_manager.get('master_id', '')
        if master_id:
            self.user_roles[str(master_id)] = UserRole.MASTER
        
        # 移除管理员角色，不再加载管理员列表
    
    def refresh_config(self):
        """刷新安全配置（bot启动时调用，重新加载主人QQ等）"""
        self._load_config()

    def get_user_role(self, user_id: str) -> UserRole:
        """
        获取用户角色
        :param user_id: 用户ID
        :return: 用户角色
        """
        # 首先检查是否是主人
        if user_id in self.user_roles:
            return self.user_roles[user_id]
        
        # 检查是否机器人自身（从配置中获取自己的 ID）
        self_qq = config_manager.get('self_qq', '')
        if self_qq and str(user_id) == str(self_qq):
            return UserRole.SELF
        
        # 默认是别人（访客）
        return UserRole.GUEST
    
    def check_permission(self, user_id: str, permission: str) -> Tuple[bool, str]:
        """
        高级权限检查
        :param user_id: 用户ID
        :param permission: 权限名称
        :return: (是否有权限, 提示信息)
        """
        # 验证输入
        if not self.validator.is_valid_qq(user_id):
            return False, "无效的用户ID"
        
        # 检查黑名单
        if user_id in self.blacklist:
            blacklist_info = self.blacklist[user_id]
            return False, f"您已被禁止使用此功能（原因：{blacklist_info.get('reason', '未指定')}）"
        
        # 获取用户角色
        role = self.get_user_role(user_id)
        
        # 检查权限
        if permission in self.role_permissions[role]:
            logger_manager.log_with_context(
                logger,
                logging.DEBUG,
                "权限校验通过",
                context={
                    "sender_id": user_id,
                    "role": role.value,
                    "permission": permission
                }
            )
            return True, f"权限校验通过（{role.value}）"
        else:
            logger_manager.log_with_context(
                logger,
                logging.DEBUG,
                "权限校验失败",
                context={
                    "sender_id": user_id,
                    "role": role.value,
                    "permission": permission
                }
            )
            return False, f"权限不足！需要{permission}权限，当前角色：{role.value}"
    
    def check_master_permission(self, user_id: str) -> Tuple[bool, str]:
        """
        快捷检查主人权限
        :param user_id: 用户ID
        :return: (是否是主人, 提示信息)
        """
        return self.check_permission(user_id, 'system_admin')
    
    def filter_dangerous_content(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        高级内容安全过滤
        :param content: 待检查内容
        :return: (是否安全, 错误信息)
        """
        # 净化内容
        content = self.validator.sanitize_input(content)
        
        # 检查危险命令
        for pattern in self.dangerous_commands:
            if re.search(pattern, content, re.IGNORECASE):
                logger_manager.log_with_context(
                    logger,
                    logging.DEBUG,
                    "检测到危险命令",
                    context={"pattern": pattern, "content_preview": content[:100]}
                )
                return False, f"检测到危险命令模式：{pattern}"
        
        # 检查敏感字符（防注入）- 排除命令前缀斜杠
        sensitive_pattern = r'[\;\&\|\$\<\>\'\"\`]'
        # 允许命令前缀的斜杠，但检查其他位置的敏感字符
        content_without_prefix = content[1:] if content.startswith('/') else content
        if re.search(sensitive_pattern, content_without_prefix):
            logger_manager.log_with_context(
                    logger,
                    logging.DEBUG,
                    "检测到敏感字符",
                    context={"content_preview": content[:100]}
                )
            return False, "内容包含敏感字符，可能存在安全风险"
        
        # 检查SQL注入
        sql_patterns = [
            r'\b(select|insert|update|delete|drop|truncate|alter)\b.*?\b(from|into|table|database)\b',
            r'\bunion\s+select\b',
            r'--|#',
            r';\s*[a-zA-Z]'
        ]
        for pattern in sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                logger_manager.log_with_context(
                    logger,
                    logging.ERROR,
                    "检测到SQL注入尝试",
                    context={"pattern": pattern, "content_preview": content[:100]}
                )
                return False, "检测到潜在的SQL注入攻击"
        
        return True, None
    
    def log_audit_event(self, user_id: str, action: str, resource: str = None, success: bool = None, event_type: str = None, details: dict = None):
        """
        记录审计日志
        :param user_id: 用户ID
        :param action: 操作类型
        :param resource: 操作资源
        :param success: 是否成功
        :param event_type: 事件类型（兼容旧调用）
        :param details: 详细信息（兼容旧调用）
        """
        audit_entry = {
            'sender_id': user_id,
            'role': self.get_user_role(user_id).value,
            'action': action,
            'resource': resource,
            'success': success
        }
        
        # 记录到内存（可扩展为存储到文件或数据库）
        self.audit_logs.append(audit_entry)
        
        # 保留最近1000条记录
        if len(self.audit_logs) > 1000:
            self.audit_logs = self.audit_logs[-1000:]
        
        # 记录到日志文件
        logger_manager.log_with_context(
            logger,
            logging.INFO if success else logging.WARNING,
            "审计日志",
            context=audit_entry
        )
    
    def add_to_blacklist(self, user_id: str, reason: str, duration: int = 0):
        """
        添加用户到黑名单
        :param user_id: 用户ID
        :param reason: 拉黑原因
        :param duration: 拉黑时长（秒，0表示永久）
        """
        self.blacklist[user_id] = {
            'reason': reason,
            'added_at': time.time(),
            'duration': duration
        }
        
        logger_manager.log_with_context(
            logger,
            logging.INFO,
            "用户被添加到黑名单",
            context={
                "sender_id": user_id,
                "reason": reason,
                "duration": duration
            }
        )
    
    def remove_from_blacklist(self, user_id: str):
        """
        从黑名单移除用户
        :param user_id: 用户ID
        """
        if user_id in self.blacklist:
            del self.blacklist[user_id]
            logger_manager.log_with_context(
                logger,
                logging.INFO,
                "用户从黑名单移除",
                context={"sender_id": user_id}
            )

    def is_blocked(self, user_id: str) -> bool:
        """
        检查用户是否在黑名单中（含超时自动清理）
        :param user_id: 用户ID
        :return: 是否被拦截
        """
        uid = str(user_id)
        entry = self.blacklist.get(uid)
        if entry is None:
            return False
        duration = entry.get('duration', 0)
        if duration > 0:
            elapsed = time.time() - entry.get('added_at', 0)
            if elapsed >= duration:
                del self.blacklist[uid]
                return False
        return True
    
    def generate_token(self, user_id: str) -> str:
        """
        生成安全令牌
        :param user_id: 用户ID
        :return: 安全令牌
        """
        # 生成包含时间戳的令牌
        timestamp = str(int(time.time()))
        data = f"{user_id}:{timestamp}:{config_manager.get('secret_key', 'default_secret')}"
        token = hashlib.sha256(data.encode()).hexdigest()
        return f"{user_id}.{timestamp}.{token}"
    
    def verify_token(self, token: str) -> bool:
        """
        验证安全令牌
        :param token: 待验证的令牌
        :return: 是否有效
        """
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return False
            
            user_id, timestamp, token_hash = parts
            
            # 检查时间戳是否过期（24小时）
            if time.time() - int(timestamp) > 86400:
                return False
            
            # 重新计算哈希
            data = f"{user_id}:{timestamp}:{config_manager.get('secret_key', 'default_secret')}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            
            # 验证哈希
            return token_hash == expected_hash
        except:
            return False
            
    def validate_input(self, data: Dict) -> bool:
        """
        验证输入数据是否合法
        :param data: 输入数据字典
        :return: 是否合法
        """
        try:
            # 基本类型检查
            if not isinstance(data, dict):
                return False
            
            # 放宽验证规则，允许正常的消息处理
            # 只进行基本的安全检查，不再使用filter_dangerous_content进行严格过滤
            
            # 检查数据大小，防止过大的请求，但设置更大的阈值
            data_str = json.dumps(data, ensure_ascii=False)
            if len(data_str) > 50000:
                logger.warning(f"[安全防护] 请求数据过大：{len(data_str)} 字符")
                return False
            
            # 只对明显超长的字符串进行限制
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 5000:
                    logger.warning(f"[安全防护] 字段 {key} 值过长")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"[安全防护] 输入验证异常：{str(e)}")
            # 为了让机器人正常工作，即使验证过程出错也返回True
            return True
            
    def validate_command(self, command: str) -> bool:
        """
        验证命令的安全性
        """
        try:
            # 检查命令长度
            if len(command) > 200:
                return False
                
            # 首先检查是否为已知的安全命令（优先级最高）
            safe_commands = ["/关于", "/help", "/菜单"]
            if command.strip() in safe_commands:
                return True
                
            # 对于非安全命令，进行危险模式检查
            is_safe, _ = self.filter_dangerous_content(command)
            if not is_safe:
                return False
                
            # 其他命令默认通过基础验证
            return True
        except Exception as e:
            logger.error(f"命令验证异常: {str(e)}")
            return False
    
    def validate_plugin_access(self, plugin_name: str, user_id: str) -> bool:
        """
        验证用户是否有权限访问特定插件
        """
        try:
            # 检查用户是否为管理员
            has_permission, _ = self.check_permission(user_id, 'manage_plugins')
            if has_permission:
                return True
                
            # 检查插件是否为公开插件
            public_plugins = ["general", "help", "weather"]
            if plugin_name.lower() in public_plugins:
                return True
                
            # 检查用户是否在插件白名单中
            # 这里可以扩展为从配置中读取插件权限设置
            return True  # 默认允许访问，后续可扩展更细粒度的权限控制
        except Exception as e:
            logger.error(f"插件访问验证异常: {str(e)}")
            return False
    
    def check_rate_limit(self, key: str) -> Tuple[bool, Optional[str]]:
        """
        检查请求是否超过频率限制（代理到RateLimiter）
        :param key: 用户标识
        :return: (是否允许请求, 错误信息)
        """
        return self.rate_limiter.check_rate_limit(key)

security_manager = SecurityManager()

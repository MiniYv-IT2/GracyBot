import re
import logging
from typing import Optional, Tuple

# 导入配置和新的安全管理器
from core.config import MASTER_ID
from core.security_manager import security_manager, InputValidator

# ========== 安全常量配置（集中管理，便于维护） ==========
# 危险命令拦截列表（Linux终端/系统操作相关，可按需扩展）
DANGEROUS_COMMANDS = [
    r"rm\s+-rf",          # 强制删除命令
    r"shutdown",          # 关机命令
    r"init\s+0",          # 系统停机命令
    r"reboot",            # 重启命令
    r"mkfs|mke2fs",       # 格式化命令
    r"dd\s+if=.*of=.*",   # 磁盘写入命令
    r"chmod\s+777",       # 危险权限设置
    r"sudo\s+su",         # 提权至root
]

# 敏感字符过滤列表（防注入/恶意字符）
SENSITIVE_CHARS = r'[\;\&\|\$\<\>\'\"]'

# ========== 权限校验工具（全局统一复用） ==========
def check_permission(user_id: str, require_master: bool = False) -> Tuple[bool, str]:
    """
    统一权限校验逻辑（替代各插件分散实现）
    :param user_id: 待校验用户ID
    :param require_master: 是否需要主人权限
    :return: (校验结果, 提示信息)
    """
    try:
        # 使用新的安全管理器进行权限检查
        if require_master:
            # 检查主人权限（system_admin权限）
            success, message = security_manager.check_master_permission(user_id)
            if success:
                # 记录审计日志
                security_manager.log_audit_event(
                    user_id=user_id,
                    action="access_master_feature",
                    resource="master_only_function",
                    success=True
                )
                return True, "✅ 权限校验通过（主人身份）"
            else:
                # 记录审计日志
                security_manager.log_audit_event(
                    user_id=user_id,
                    action="access_master_feature",
                    resource="master_only_function",
                    success=False
                )
                return False, "❌ 该功能仅主人可使用，权限不足！"
        
        # 普通用户权限校验（使用use_plugins权限）
        success, message = security_manager.check_permission(user_id, 'use_plugins')
        if success:
            return True, "✅ 权限校验通过（普通用户）"
        else:
            return False, "❌ 权限不足，无法使用该功能！"
    except Exception as e:
        # 异常情况下使用传统校验作为降级方案
        logging.getLogger("GracyBot-HTTP").error(f"[权限校验] 安全管理器异常，使用降级方案: {str(e)}")
        
        # 主人权限校验（降级方案）
        if require_master:
            if user_id != str(MASTER_ID):
                logging.getLogger("GracyBot-HTTP").warning(f"[安全校验] 用户{user_id}尝试访问主人专属功能，权限拒绝")
                return False, "❌ 该功能仅主人可使用，权限不足！"
            return True, "✅ 权限校验通过（主人身份）"
        
        # 普通用户权限校验（基础校验）
        return True, "✅ 权限校验通过（普通用户）"

# ========== 命令安全过滤工具（防恶意命令注入） ==========
def filter_dangerous_commands(cmd: str) -> Tuple[bool, Optional[str]]:
    """
    危险命令过滤（适配Linux终端等插件，提前拦截风险操作）
    :param cmd: 待过滤命令
    :return: (是否安全, 危险提示/None)
    """
    try:
        # 首先进行基本验证
        if not cmd or len(cmd) > 1000:
            return False, "⚠️  命令长度无效！"
        
        # 使用新的安全管理器进行高级内容过滤
        success, message = security_manager.filter_dangerous_content(cmd)
        if not success:
            return False, f"⚠️  {message}"
        
        return True, None
    except Exception as e:
        # 异常情况下使用传统过滤作为降级方案
        logging.getLogger("GracyBot-HTTP").error(f"[命令过滤] 安全管理器异常，使用降级方案: {str(e)}")
        
        # 正则匹配危险命令（忽略大小写）
        for dangerous_pattern in DANGEROUS_COMMANDS:
            if re.search(dangerous_pattern, cmd, re.IGNORECASE):
                logging.getLogger("GracyBot-HTTP").error(f"[安全过滤] 拦截危险命令：{cmd[:50]}...")
                return False, f"⚠️  检测到危险命令！为保护系统安全，禁止执行「{dangerous_pattern}」相关操作"
        
        # 敏感字符过滤（防命令注入）
        if re.search(SENSITIVE_CHARS, cmd):
            logging.getLogger("GracyBot-HTTP").warning(f"[安全过滤] 拦截含敏感字符的命令：{cmd[:50]}...")
            return False, "⚠️  命令中包含敏感字符，可能存在安全风险，禁止执行！"
        
        return True, None

# ========== 输入内容净化工具（防XSS/恶意输入） ==========
def sanitize_input(content: str, max_length: int = 1000) -> str:
    """
    输入内容净化（过滤特殊字符，防XSS注入，适配所有用户输入场景）
    :param content: 原始输入内容
    :param max_length: 最大长度限制
    :return: 净化后的安全内容
    """
    try:
        # 使用新的输入验证器进行高级净化
        return InputValidator.sanitize_input(content, max_length)
    except Exception as e:
        # 异常情况下使用传统净化作为降级方案
        logging.getLogger("GracyBot-HTTP").error(f"[输入净化] 验证器异常，使用降级方案: {str(e)}")
        
        # HTML特殊字符转义（防XSS）
        sanitize_map = {
            "<": "&lt;",
            ">": "&gt;",
            "&": "&amp;",
            "'": "&#39;",
            '"': "&quot;",
            "/": "&#47;"
        }
        for char, replace in sanitize_map.items():
            content = content.replace(char, replace)
        
        # 过滤空字符/控制字符
        content = re.sub(r'[\x00-\x1F\x7F]', '', content)
        
        # 限制长度
        if len(content) > max_length:
            content = content[:max_length]
        
        return content

# ========== 日志安全脱敏工具（终极版：覆盖所有QQ/ID格式，无死角） ==========
def sanitize_log(content: str) -> str:
    """
    日志内容脱敏（隐藏所有用户ID/QQ/群ID，保护隐私安全）
    :param content: 原始日志内容
    :return: 脱敏后的日志内容
    """
    def _mask_bare_number(m):
        """脱敏裸数字，但排除 IP:port 和 WS address 格式中的端口号"""
        num = m.group(0)
        start = m.start()
        prefix = content[max(0, start-40):start]
        if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[\',\s\)]*$', prefix):
            return num
        if re.search(r"'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}[\',\s]*$", prefix):
            return num
        return f"用户****{num[-4:]}"

    # 【优先匹配】带标签的ID格式（必须在裸数字之前，避免被裸数字规则先匹配）
    # 0. @QQ号脱敏（格式：[@123456] → [@用户****456]）
    content = re.sub(r'\[@(\d{1,})\]', lambda m: f'[@用户****{m.group(1)[-4:]}]', content)
    content = re.sub(r'@(\d{5,15})(?!\w)', lambda m: f'@用户****{m.group(1)[-4:]}', content)
    # 1. 群组ID/群ID/群号脱敏
    content = re.sub(r'群(?:组)?ID[：:]\s*(\d{1,})', lambda m: f"群ID：****{m.group(1)[-4:]}", content)
    content = re.sub(r'群号[：:\s]+(\d{1,})', lambda m: f"群号：****{m.group(1)[-4:]}", content)
    # 2. 群名称/群聊名称
    content = re.sub(r'(?:群名|群聊名称)[：:]\s*([^\s|]{1,30})', lambda m: f"群名：{m.group(1)}", content)
    # 3. 带前缀用户ID脱敏
    content = re.sub(r'用户(\d{1,})', lambda m: f"用户****{m.group(1)[-4:]}", content)
    # 4. 括号包裹ID脱敏
    content = re.sub(r'【(\d{1,})】', lambda m: f"【用户****{m.group(1)[-4:]}】", content)
    # 5. 目标ID脱敏
    content = re.sub(r'目标ID[：:]\s*(\d{1,})', lambda m: f"目标ID：用户****{m.group(1)[-4:]}", content)
    # 5.1 消息发送日志脱敏
    content = re.sub(r'目标:\s*(\d{5,15})', lambda m: f"目标: 用户****{m.group(1)[-4:]}", content)
    # 6. 消息发送目标脱敏
    content = re.sub(r'发送(private|group)消息到(\d{1,})', lambda m: f"发送{m.group(1)}消息到【用户****{m.group(2)[-4:]}】", content)
    # 7. 密码脱敏
    content = re.sub(r'密码[:=]\s*[^\s]+', '密码: ******', content)
    # 8. API密钥脱敏
    content = re.sub(r'(API_KEY|api_key|sk-|SK-)[\s:]*([a-zA-Z0-9]{6})[a-zA-Z0-9]*', r'\1\2****', content)
    # 9. 内置命令日志脱敏
    content = re.sub(r'主人(\d{1,})', lambda m: f"主人用户****{m.group(1)[-4:]}", content)
    # 10. 裸QQ/ID脱敏（放最后，只匹配没有被标签覆盖的纯数字）
    content = re.sub(r'(?<!\w)(\d{5,15})(?!\w)', _mask_bare_number, content)
    return content

# ========== 日志自动脱敏过滤器（全局生效，无需手动调用） ==========
class SanitizeLogFilter(logging.Filter):
    """日志过滤器：所有日志输出前自动脱敏，彻底隐藏QQ/ID"""
    def __init__(self, name: str = ""):
        super().__init__(name)
        # 增加更多类型的敏感信息脱敏规则
        self.sensitive_patterns = [
            # API密钥模式
            (r'(sk-|API_KEY=|token=)[\w-]{4,}', r'\1****'),
            # 邮箱模式
            (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '****@****.***'),
            # 手机号模式
            (r'(?<!\d)(1[3-9]\d{9})(?!\d)', '1****' + '\1'[-4:] if '\1' else '1**********'),
            # URL中的查询参数
            (r'(password|secret|token)=([^&]+)', r'\1=****'),
        ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        # 对日志消息进行自动脱敏（兼容带参数/无参数日志）
        try:
            # 先使用基础脱敏
            if record.args:
                try:
                    formatted_msg = record.msg % record.args
                    record.msg = sanitize_log(formatted_msg)
                    record.args = ()  # 清空参数，避免重复格式化
                except (TypeError, ValueError):
                    # 处理参数格式错误的情况
                    record.msg = f"{record.msg} [参数: {sanitize_log(str(record.args))}]"
                    record.args = ()
            else:
                # 直接脱敏普通日志（含裸ID格式）
                record.msg = sanitize_log(str(record.msg))
            
            # 应用额外的敏感信息脱敏规则
            for pattern, replacement in self.sensitive_patterns:
                # 使用函数处理replacement中的捕获组引用
                def replace_with_groups(match):
                    if '\1' in replacement:
                        # 保留第一个捕获组的一部分
                        if match.group(1):
                            if '\1****' in replacement:
                                return match.group(1) + '****'
                    return replacement
                
                # 使用re.sub和回调函数
                import re
                record.msg = re.sub(pattern, replace_with_groups, record.msg)
        except Exception as e:
            # 脱敏失败不影响日志输出，仅记录异常（使用通用日志器避免循环）
            logging.getLogger("GracyBot-HTTP").error(f"[日志脱敏过滤器] 处理异常：{str(e)}")
        return True

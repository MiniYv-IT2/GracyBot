import collections
import os
import sys
from typing import Dict, List, Optional

# 动态获取虚拟环境site-packages路径（支持所有Python版本）
def get_venv_site_packages():
    """动态获取虚拟环境site-packages路径"""
    try:
        # 优先使用site模块
        import site
        return site.getsitepackages()[0]
    except:
        try:
            # 从sys.executable推导
            import pathlib
            venv_path = pathlib.Path(sys.executable).parent.parent
            python_version = f'python{sys.version_info.major}.{sys.version_info.minor}'
            return str(venv_path / 'lib' / python_version / 'site-packages')
        except:
            # 最后遍历sys.path
            for path in sys.path:
                if 'site-packages' in path:
                    return path
    return None

# 添加虚拟环境路径
venv_site_packages = get_venv_site_packages()
if venv_site_packages and venv_site_packages not in sys.path:
    sys.path.insert(0, venv_site_packages)

# 导入GracyBot核心模块
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.utils import logger
from core.config import *
from core.gracy_adapter.message import GracyImage

from .core.draw import GracyBotHelpDrawer


class HelpPlugin:
    def __init__(self):
        self.config = {}
        self.drawer = GracyBotHelpDrawer(self.config)

    def handle_help(self, message, user_info, group_info):
        """获取插件帮助信息"""
        # 精准匹配帮助命令别名
        valid_commands = ["/help", "/帮助", "/菜单", "/helps"]
        if message.strip() not in valid_commands:
            return None
            
        help_msg = self.get_all_commands()
        if not help_msg:
            return "没有找到任何插件或命令"
        
        try:
            image = self.drawer.draw_help_image(help_msg)
            # 保存图片到临时文件
            temp_path = os.path.join(os.path.dirname(__file__), "data", "temp_help.png")
            with open(temp_path, "wb") as f:
                f.write(image)
            
            # 生成帮助图并返回 GracyImage（由调用方统一发送）
            return GracyImage(file_path=temp_path)
                
        except Exception as e:
            logger.error(f"生成帮助图片失败: {e}")
            return "生成帮助图片失败，请联系管理员"

    def get_all_commands(self) -> Dict[str, List[str]]:
        """获取所有其他插件及其命令列表, 格式为 {plugin_name: [command#desc]}"""
        # 使用 defaultdict 可以方便地向列表中添加元素
        plugin_commands: Dict[str, List[str]] = collections.defaultdict(list)
        
        try:
            # 导入插件管理器获取所有插件信息
            from core.plugin_manager import PLUGIN_REGISTRY
            
            # 获取所有已注册的插件
            for plugin_meta in PLUGIN_REGISTRY:
                plugin_name = plugin_meta.get("name", "未知插件")
                commands = plugin_meta.get("commands", [])
                description = plugin_meta.get("description", "")
                
                # 跳过自身插件
                if plugin_name == "帮助插件":
                    continue
                    
                # 添加命令和描述（优先取命令独立描述，没有则回退插件统一描述）
                cmd_descs = plugin_meta.get("command_descriptions", {})
                for cmd in commands:
                    cmd_desc = cmd_descs.get(cmd, "") or description
                    if cmd_desc:
                        formatted_command = f"{cmd}#{cmd_desc}"
                    else:
                        formatted_command = cmd
                    plugin_commands[plugin_name].append(formatted_command)
                    
        except Exception as e:
            logger.error(f"获取插件列表失败: {e}")
            return {}
            
        return dict(plugin_commands)


# 模块级别的处理函数，供插件管理器调用
_help_plugin_instance = None

def handle_help(plugin_manager, gracy_send_msg, data, sender_id, chat_type, permission, logger):
    """模块级别的帮助处理函数，适配GracyBot的7参数接口"""
    global _help_plugin_instance
    if _help_plugin_instance is None:
        _help_plugin_instance = HelpPlugin()
    
    # 从data中提取原始消息
    raw_msg = data.get("text", "")
    logger.info(f"[帮助插件] 收到消息: '{raw_msg}'")
    
    # 调用插件处理函数
    result = _help_plugin_instance.handle_help(raw_msg, {"id": sender_id}, {"type": chat_type})
    logger.info(f"[帮助插件] 处理结果: {result}")
    
    # 发送结果
    if result:
        # 根据聊天类型确定正确的目标ID
        if chat_type == "group":
            target_id = data.get("raw_data", {}).get("group_id", sender_id)
        else:
            target_id = data.get("target_id", sender_id)

        logger.info(f"[帮助插件] 发送消息到 {target_id}")
        if isinstance(result, GracyImage):
            from core.gracy_adapter.send import gracy_send_msg
            gracy_send_msg(target_id, result, chat_type=chat_type)
        else:
            from core.gracy_adapter.send import gracy_send_msg
            from core.gracy_adapter.message import GracyText
            gracy_send_msg(target_id, GracyText(text=str(result)), chat_type=chat_type)
    else:
        logger.warning("[帮助插件] 没有生成回复内容")

import json
import requests
import time
import threading
import sys
import os
import subprocess
import platform
from flask import request, jsonify
from typing import Dict
from core.config import (
    MASTER_ID,
    AUTO_REPLIES,
    ROBOT_ID,
    BOT_VERSION
)
from core.utils import logger
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.message import GracyText
from core.gracy_adapter.onebot.http import GracyOneBot
from core.security import sanitize_log

# 模块级 OneBot 解析器（单例，复用避免每次新建）
_onebot_parser = GracyOneBot(robot_id=ROBOT_ID)
from core.plugin_manager import plugin_manager, PLUGIN_REGISTRY
from core.security_manager import security_manager
from core.monitor import monitor_manager
from core.logger_manager import logger_manager


def register_plugin(plugin_meta: Dict):
    PLUGIN_REGISTRY.append(plugin_meta)


def callback_base():
    try:
        # 获取客户端IP进行频率限制检查
        client_ip = request.remote_addr
        if not security_manager.check_rate_limit(client_ip):
            logger.warning(f"[安全防护] 客户端IP {client_ip} 频率超限")
            return jsonify({"retcode": 429, "msg": "请求频率过高，请稍后再试"}), 429

        data = request.get_json()
        if not data:
            logger.error(sanitize_log(f"[回调基础] 接收消息为空，请求体：{request.data[:50]}..."))
            return jsonify({"retcode": 1, "msg": "消息为空"}), 400

        # 输入验证
        if not security_manager.validate_input(data):
            logger.warning(f"[安全防护] 输入数据验证失败，可能包含恶意内容")
            return jsonify({"retcode": 403, "msg": "输入内容不合法"}), 403

        # 心跳/metaevent 静默处理
        if data.get("post_type") == "meta_event":
            return jsonify({"retcode": 0})

        # 处理戳一戳事件（notify类型）
        if data.get("post_type") == "notice" and data.get("notice_type") == "notify":
            sub_type = data.get("sub_type", "")
            if sub_type in ["poke", "lucky_king"]:
                try:
                    from plugins.OpenAI_plugin.poke_handler import handle_poke_event
                    handle_poke_event(data)
                    logger.info(sanitize_log(
                        f"[戳一戳事件] 处理戳一戳事件（用户ID：{data.get('user_id')}，目标ID：{data.get('target_id')}）"))
                except ImportError:
                    logger.warning("[戳一戳事件] OpenAI插件错误，戳一戳功能不可用")
                except Exception as e:
                    logger.error(sanitize_log(f"[戳一戳事件] 处理失败：{str(e)}"))
            return jsonify({"retcode": 0})

        # 通过 GracyOneBot 统一解析入站消息（消灭裸 CQ 码处理）
        event = _onebot_parser.parse_event(data)
        if not event:
            return jsonify({"retcode": 0})

        chat_type = event.chat_type
        sender_id = event.sender_id

        # 过滤机器人自身消息（必须在记日志之前）
        if sender_id == str(ROBOT_ID):
            return jsonify({"retcode": 0})

        # 只传递必要的信息，避免日志过于冗长
        simplified_context = {
            'self_id': data.get('self_id'),
            'user_id': data.get('user_id'),
            'message_type': data.get('message_type'),
            'raw_message': data.get('raw_message', ''),
            'group_id': data.get('group_id'),
            'group_name': data.get('group_name', '')
        }
        logger_manager.log_with_context(
            logger,
            'INFO',
            "[适配器回调] 收到消息",
            context=simplified_context
        )

        target_id = event.target_id
        raw_msg = event.raw_text.strip()
        nickname = event.nickname or "未知用户"

        # 对用户消息进行频率限制检查
        if not security_manager.check_rate_limit(f"user_{sender_id}"):
            logger.warning(f"[安全防护] 用户 {sender_id} 消息频率超限")
            if chat_type == "private":
                gracy_send_msg(sender_id, GracyText(text="您的消息发送频率过高，请稍后再试"), chat_type="private")
            return jsonify({"retcode": 0})

        is_at_bot = event.is_at_bot
        # GracyOneBot.parse_event 已自动处理 @bot 检测和文本清洗

        return {
            "chat_type": chat_type,
            "sender_id": sender_id,
            "target_id": target_id,
            "raw_msg": raw_msg,
            "nickname": nickname,
            "is_at_bot": is_at_bot,
            "data": data
        }
    except Exception as e:
        logger.error(sanitize_log(f"[适配器回调] 处理异常：{type(e).__name__}，原因：{str(e)}"))
        return jsonify({"retcode": 1, "msg": f"回调处理异常：{str(e)}"}), 500


def _build_clean_data(parsed_data: dict) -> dict:
    """从原始数据构建结构化插件数据"""
    raw_data = parsed_data.get("data", {})
    raw_msg = parsed_data.get("raw_msg", "")
    nick = parsed_data.get("nickname", "用户")

    images = []
    ats = []
    msg_arr = raw_data.get("message", [])
    if isinstance(msg_arr, list):
        for seg in msg_arr:
            if isinstance(seg, dict):
                if seg.get("type") == "image":
                    fid = seg.get("data", {}).get("file", "")
                    if fid:
                        images.append(fid)
                elif seg.get("type") == "at":
                    qq = seg.get("data", {}).get("qq", "")
                    if qq:
                        ats.append(str(qq))

    return {
        "text": raw_msg,
        "nickname": nick,
        "images": images,
        "ats": ats,
        "target_id": parsed_data.get("target_id", ""),
        "chat_type": parsed_data.get("chat_type", ""),
        "raw_data": raw_data,
    }


def dispatch_plugin_cmd(parsed_data):
    try:
        chat_type = parsed_data["chat_type"]
        sender_id = parsed_data["sender_id"]
        target_id = parsed_data["target_id"]
        raw_msg = parsed_data["raw_msg"]
        is_at_bot = parsed_data["is_at_bot"]
        nickname = parsed_data.get("nickname", "用户")
        plugin_data = _build_clean_data(parsed_data)
        handled = False

        # ═══════════════ 黑名单全局预检 ═══════════════
        try:
            from plugins.Xiaoyu_plugin.Xiaoyu_plugin import is_user_blocked
            if is_user_blocked(str(sender_id)):
                logger.info(f"[黑名单拦截] 用户 {sender_id} 在黑名单中，消息已拦截")
                return jsonify({"retcode": 0}), True
        except ImportError:
            pass  # 小禹插件未加载时不拦截

        security_manager.log_audit_event(
            user_id=sender_id,
            action="message_received",
            resource=None,
            success=True,
            event_type="message",
            details={"chat_type": chat_type, "target_id": target_id, "command": raw_msg[:50]}
        )

        if raw_msg == "/关机":
            is_master, msg = security_manager.check_master_permission(sender_id)
            if is_master:
                gracy_send_msg(target_id, GracyText(text="🛑 正在执行关机操作...机器人将在3秒后关闭"), chat_type=chat_type)
                handled = True
                logger.info(sanitize_log(f"[内置命令] 主人{sender_id}执行/关机命令，即将关闭机器人"))

                def delayed_shutdown():
                    time.sleep(3)
                    try:
                        result = subprocess.run(['systemctl', 'stop', 'bot.service'], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            logger.info("[关机指令] 使用systemd方式关机成功")
                            return
                        else:
                            logger.warning(f"[关机指令] systemd方式失败: {result.stderr}")
                    except Exception as e:
                        logger.warning(f"[关机指令] systemd方式不可用: {str(e)}")
                    
                    try:
                        from core.main import safe_shutdown
                        safe_shutdown()
                        return
                    except ImportError:
                        logger.error("[关机指令] 无法导入safe_shutdown函数")
                    
                    try:
                        shutdown_flag_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".shutdown_flag")
                        with open(shutdown_flag_file, "w") as f:
                            f.write("1")
                        
                        logger.info("[关机指令] 使用Python原生方式关机")
                        sys.exit(0)
                        
                    except Exception as e:
                        logger.error(f"[关机指令] 关机失败: {str(e)}")
                        sys.exit(1)

                threading.Thread(target=delayed_shutdown, daemon=True).start()
            else:
                gracy_send_msg(target_id, GracyText(text="⚠️ 权限不足！只有机器人主人才可以执行关机操作"), chat_type=chat_type)
                logger.warning(f"[安全防护] 用户{sender_id}尝试执行关机指令，权限不足")
                handled = True

        elif raw_msg == "/重启":
            is_master, msg = security_manager.check_master_permission(sender_id)
            if is_master:
                gracy_send_msg(target_id, GracyText(text="🔄 正在执行重启操作...机器人将在5秒后重启"), chat_type=chat_type)
                handled = True
                logger.info(sanitize_log(f"[内置命令] 主人{sender_id}执行/重启命令，即将重启机器人"))

                def delayed_restart():
                    time.sleep(5)
                    try:
                        result = subprocess.run(['systemctl', 'restart', 'bot.service'], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            logger.info("[重启指令] 使用systemd方式重启成功")
                            return
                        else:
                            logger.warning(f"[重启指令] systemd方式失败: {result.stderr}")
                    except Exception as e:
                        logger.warning(f"[重启指令] systemd方式不可用: {str(e)}")
                    
                    try:
                        logger.info("[重启指令] 使用Python原生方式重启")
                        
                        restart_flag_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".restart_flag")
                        with open(restart_flag_file, "w") as f:
                            f.write("1")
                        
                        if platform.system() == "Windows":
                            subprocess.Popen([sys.executable] + sys.argv, creationflags=subprocess.CREATE_NEW_CONSOLE)
                            sys.exit(0)
                        else:
                            os.execv(sys.executable, ['python'] + sys.argv)
                            
                    except Exception as e:
                        logger.error(f"[重启指令] 执行重启失败: {str(e)}")
                        sys.exit(0)

                threading.Thread(target=delayed_restart, daemon=True).start()
            else:
                gracy_send_msg(target_id, GracyText(text="⚠️ 权限不足！只有机器人主人才可以执行重启操作"), chat_type=chat_type)
                logger.warning(f"[安全防护] 用户{sender_id}尝试执行重启指令，权限不足")
                handled = True

        elif raw_msg == "/开机":
            is_master, msg = security_manager.check_master_permission(sender_id)
            if is_master:
                gracy_send_msg(target_id, GracyText(text="🚀 正在执行开机操作...机器人服务将在3秒后启动"), chat_type=chat_type)
                handled = True
                logger.info(sanitize_log(f"[内置命令] 主人{sender_id}执行/开机命令，即将启动机器人服务"))

                def delayed_startup():
                    time.sleep(3)
                    try:
                        import subprocess
                        result = subprocess.run(['systemctl', 'start', 'bot.service'], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            logger.info("[开机指令] 使用systemd方式启动成功")
                            return
                        else:
                            logger.warning(f"[开机指令] systemd方式失败: {result.stderr}")
                    except Exception as e:
                        logger.warning(f"[开机指令] systemd方式不可用: {str(e)}")
                    
                    try:
                        import os
                        import sys
                        import subprocess
                        import platform
                        
                        current_pid = os.getpid()
                        logger.info(f"[开机指令] 当前进程PID: {current_pid}")
                        
                        if platform.system() == "Windows":
                            subprocess.Popen([sys.executable] + sys.argv, creationflags=subprocess.CREATE_NEW_CONSOLE)
                        else:
                            subprocess.Popen(["nohup", sys.executable] + sys.argv + ["&"], 
                                          shell=False, 
                                  stdout=subprocess.DEVNULL, 
                                  stderr=subprocess.DEVNULL)
                            
                        logger.info("[开机指令] 新的机器人进程已启动")
                            
                    except Exception as e:
                        logger.error(f"[开机指令] 执行开机失败: {str(e)}")

                threading.Thread(target=delayed_startup, daemon=True).start()
            else:
                gracy_send_msg(target_id, GracyText(text="⚠️ 权限不足！只有机器人主人才可以执行开机操作"), chat_type=chat_type)
                logger.warning(f"[安全防护] 用户{sender_id}尝试执行开机指令，权限不足")
                handled = True

        elif raw_msg == "/关于":
            if security_manager.validate_command(raw_msg):
                about_content = f"""🏷️ 机器人基础信息
• 机器人框架：GracyBot
• 当前版本：{BOT_VERSION}
• 核心定位：基于 Python 3.11+ 的安全 QQ 机器人框架，对接 NapCat，欢迎大佬来开发插件
• 开发模式：插件即目录，一个插件一个文件夹，放入 plugins/ 自动注册，无需改框架代码
🛠️ 框架产品特征
• 核心开发语言：Python 3.11+ / TypeScript
• 安全防护：全局日志脱敏、危险命令拦截、权限分级校验、频率限制
• 插件管理：动态加载、指令自动分发、插件隔离运行、热重载
• 基础工具：结构化日志、统一消息发送接口（GracyAdapter 多平台适配层）
• 兼容环境：Linux（Debian 11+）、Windows 10+（UTF-8 编码适配）
📋 核心特性
1. 企业级安全：敏感信息自动脱敏、系统命令风险拦截、输入验证、审计日志
2. 配置管理：集中化配置、环境变量支持、多级配置优先级
3. 插件生态：独立目录管理，热加载/热卸载，无需修改核心即可扩展
4. 多协议适配：HTTP 回调 + WebSocket 正/反向，统一 GracyAdapter 层
5. 监控与可观测性：结构化日志、性能监控、健康检查、GracyUI 管理面板
📞 维护信息
• 开发作者：小禹
• 反馈建议：欢迎到插件社区提交 Issue 或 PR"""
                gracy_send_msg(target_id, GracyText(text=about_content), chat_type=chat_type)
                handled = True
                logger.info(sanitize_log(f"[内置命令] 用户{sender_id}执行/关于命令，已返回框架信息"))
            else:
                logger.warning(f"[安全防护] 命令验证失败，拒绝执行：{raw_msg}")

        # ═══════════════ 会话管理命令 ═══════════════
        if not handled and any(cmd in raw_msg for cmd in ["/清理会话", "/清空会话", "/删除会话", "/查看会话"]):
            try:
                from core.gracy_session.gracy_session_handler import handle_session_command
                handle_session_command(
                    plugin_manager,
                    gracy_send_msg,
                    plugin_data,
                    sender_id,
                    chat_type,
                    "all",
                    logger
                )
                handled = True
                logger.info(sanitize_log(f"[内置命令] 会话管理命令处理完成: {raw_msg[:30]}"))
            except Exception as e:
                logger.error(sanitize_log(f"[内置命令] 会话管理命令处理异常: {str(e)}"))

        if not handled:
            has_basic_perm, _ = security_manager.check_permission(sender_id, "basic_query")
            has_plugin_perm, _ = security_manager.check_permission(sender_id, "use_plugins")
            has_permission = has_basic_perm or has_plugin_perm
            if has_permission:
                matched_plugin = plugin_manager.get_matched_plugin(raw_msg, chat_type, sender_id, is_at_bot)
                if matched_plugin:
                    plugin_name = matched_plugin.get("name", "unknown")
                    if security_manager.validate_plugin_access(plugin_name, sender_id):
                        handler_func = matched_plugin["handler_func"]
                        try:
                            plugin_start_time = time.time()
                            handler_func(
                                plugin_manager,
                                gracy_send_msg,
                                plugin_data,
                                sender_id,
                                chat_type,
                                "all",
                                logger
                            )
                            plugin_execution_time = time.time() - plugin_start_time
                            monitor_manager.record_plugin_execution(plugin_name, plugin_execution_time, True)
                            handled = True
                            security_manager.log_audit_event(
                                user_id=sender_id,
                                action="plugin_executed",
                                resource=plugin_name,
                                success=True,
                                event_type="plugin",
                                details={"plugin_name": plugin_name, "command": raw_msg,
                                         "execution_time": plugin_execution_time}
                            )
                            logger.info(sanitize_log(
                                f"[插件执行] 插件 {plugin_name} 执行成功，耗时: {plugin_execution_time:.3f}s"))
                        except Exception as e:
                            plugin_execution_time = time.time() - plugin_start_time
                            monitor_manager.record_plugin_execution(plugin_name, plugin_execution_time, False)
                            logger.error(sanitize_log(
                                f"[插件执行] 插件 {plugin_name} 执行异常：{str(e)}，耗时: {plugin_execution_time:.3f}s"))
                            security_manager.log_audit_event(
                                user_id=sender_id,
                                action="plugin_executed",
                                resource=plugin_name,
                                success=False,
                                event_type="plugin",
                                details={"plugin_name": plugin_name, "command": raw_msg, "error": str(e),
                                         "execution_time": plugin_execution_time}
                            )
                    else:
                        logger.warning(f"[安全防护] 用户 {sender_id} 无权访问插件 {plugin_name}")
                        security_manager.log_audit_event(
                            user_id=sender_id,
                            action="permission_denied",
                            resource="plugin",
                            success=False,
                            event_type="security",
                            details={"resource": "plugin", "plugin_name": plugin_name}
                        )
            else:
                logger.warning(f"[安全防护] 用户 {sender_id} 无插件访问权限")

        if not handled:
            try:
                # 优先级：1.特殊命令→2.自动回复→3.私聊对话→4.群聊@触发
                is_special_command = any(cmd in raw_msg for cmd in ["小禹帮助"])

                is_auto_reply_match = raw_msg in AUTO_REPLIES and (chat_type == "private" or (chat_type == "group" and is_at_bot))

                has_images = bool(plugin_data.get("images"))
                is_private_direct_chat = chat_type == "private" and (raw_msg.strip() or has_images) and not (
                            raw_msg.startswith("/") or raw_msg.startswith("//")) and not is_special_command

                # NapCat WS 可能把 @ 转为纯文本 @昵称，需要额外文本检测
                _is_at_by_text = False
                if chat_type == "group" and not is_at_bot:
                    import re
                    _is_at_by_text = bool(re.match(r'^@[\u4e00-\u9fa5\w]+\s', raw_msg))
                is_group_at_reply = chat_type == "group" and (is_at_bot or _is_at_by_text)
                
                # 文本 @ 情况下，去除 @昵称 前缀再传给 AI
                raw_msg_clean = raw_msg
                if _is_at_by_text:
                    raw_msg_clean = re.sub(r'^@[\u4e00-\u9fa5\w]+\s*', '', raw_msg).strip()

                if is_auto_reply_match or is_private_direct_chat or is_group_at_reply:
                    # 确保nickname始终有值
                    if not nickname:
                        nickname = "用户"
                    
                    if is_auto_reply_match:
                        auto_reply = AUTO_REPLIES[raw_msg]
                    else:
                        try:
                            from plugins.LLM_Chat.core.event_handler import handle_ai_chat
                            from plugins.LLM_Chat.core.api_handler import load_config
                            from plugins.LLM_Chat.core.scheduler import extract_task_from_message, schedule_task
                            
                            chat_id = f"{chat_type}_{target_id}"
                            config = load_config()
                            
                            if config.get("api_key"):
                                def bot_sender(tid, msg, chat_type, **_):
                                    gracy_send_msg(tid, GracyText(text=msg), chat_type=chat_type)
                                
                                task_info = extract_task_from_message(raw_msg_clean, chat_id)
                                logger.debug(f"[任务提取] 消息: {raw_msg_clean[:30]}... | 提取结果: {task_info}")
                                if task_info:
                                    schedule_task(chat_id, task_info["time"], task_info["content"])
                                    logger.info(f"[定时任务] 已为用户{sender_id}创建任务：{task_info['time']} - {task_info['content']}")
                                    enhanced_msg = f"{raw_msg_clean}\n[系统提示：已计算出准确的提醒时间为 {task_info['time']}，请在回复中使用这个时间]"
                                    handle_ai_chat(bot_sender, target_id, chat_type, enhanced_msg, sender_id, nickname, chat_id, plugin_data.get("raw_data"))
                                    handled = True
                                    auto_reply = None
                                else:
                                    logger.debug(f"[任务提取] 未检测到定时任务，调用AI对话")
                                    handle_ai_chat(bot_sender, target_id, chat_type, raw_msg_clean, sender_id, nickname, chat_id, plugin_data.get("raw_data"))
                                    handled = True
                                    auto_reply = None
                            else:
                                auto_reply = None
                        except Exception as e:
                            logger.warning(f"⚠️ LLM-Chat调用失败: {str(e)}")
                            auto_reply = None
                    
                    if auto_reply:
                        if chat_type == "group":
                            gracy_send_msg(target_id, GracyText(text=auto_reply), chat_type="group")
                        else:
                            gracy_send_msg(sender_id, GracyText(text=auto_reply), chat_type="private")
                        handled = True
            except ImportError:
                logger.warning("⚠️ LLM-Chat插件未加载，自动回复功能失效")

        if handled:
            logger.info(sanitize_log(f"[指令分发] 指令「{raw_msg[:20]}...」处理完成"))
        return jsonify({"retcode": 0}), handled
    except Exception as e:
        safe_msg = str(raw_msg)[:20] if raw_msg else ""
        logger.error(sanitize_log(f"[指令分发] 异常（指令：{safe_msg}...）：{type(e).__name__}，原因：{str(e)}"))
        return jsonify({"retcode": 1, "msg": f"指令处理异常：{str(e)}"}), 500, False


import os as _os
if _os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    logger.info("✅ core/handler.py 加载完成")


# ═══════════════ WS / 适配器统一事件入口 ═══════════════

def process_event_from_adapter(event: "GracyEvent") -> dict | None:
    """WS/适配器统一入口：GracyEvent → parsed_data 字典

    与 callback_base() 共享安全校验，但不依赖 Flask request。
    供 GracyOneBotWS.start(on_event) 回调使用。
    """
    from core.config import ROBOT_ID as _ROBOT_ID
    from core.gracy_adapter.send import gracy_send_msg as _gsm
    from core.gracy_adapter.message import GracyText as _GT

    # 过滤机器人自身消息
    if event.sender_id == str(_ROBOT_ID):
        return None

    simplified_context = {
        'self_id': str(_ROBOT_ID),
        'user_id': event.sender_id,
        'message_type': event.chat_type,
        'raw_message': event.raw_text or event.raw_data.get("raw_message", ""),
        'group_id': event.target_id if event.chat_type == 'group' else '',
        'group_name': event.raw_data.get('group_name', ''),
    }
    logger_manager.log_with_context(
        logger, 'INFO', "[适配器回调] 收到消息", context=simplified_context)

    # 用户频率限制
    if not security_manager.check_rate_limit(f"user_{event.sender_id}"):
        logger.warning(f"[安全防护] 用户 {event.sender_id} 消息频率超限")
        if event.chat_type == "private":
            _gsm(event.sender_id, _GT(text="您的消息发送频率过高，请稍后再试"), chat_type="private")
        return None

    # 黑名单预检
    try:
        from plugins.Xiaoyu_plugin.Xiaoyu_plugin import is_user_blocked
        if is_user_blocked(str(event.sender_id)):
            logger.info(f"[黑名单拦截] 用户 {event.sender_id} 在黑名单中，消息已拦截")
            return None
    except ImportError:
        pass

    return {
        "chat_type": event.chat_type,
        "sender_id": event.sender_id,
        "target_id": event.target_id,
        "raw_msg": event.raw_text.strip(),
        "nickname": event.nickname or "未知用户",
        "is_at_bot": event.is_at_bot,
        "data": event.raw_data,
    }

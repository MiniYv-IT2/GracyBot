#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统更新插件
用于检测GitHub仓库更新、版本管理和自动/手动更新控制
"""
# 导入必要的库
import os
import sys
import json
import time
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.utils import logger
from core.gracy_adapter.send import gracy_send_msg
from core.gracy_adapter.message import GracyText
from core.config import MASTER_ID

# 插件信息
PLUGIN_INFO = {
    "name": "update_plugin",
    "version": "1.0.0",
    "description": "系统更新插件，用于检测GitHub仓库更新",
    "author": "GracyBot开发者"
}

# 仓库信息配置
GITHUB_REPO = "https://github.com/MiniYv/GracyBot.git"  # GitHub原始地址
GITEE_REPO = "https://gitee.com/MiniYv/GracyBot.git"    # 码云仓库地址
UPDATE_CHECK_INTERVAL = 8 * 60 * 60  # 8小时（秒）
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_config.json")

# 仓库地址列表（只保留GitHub和码云）
REPO_LIST = [
    {"name": "GitHub", "url": GITHUB_REPO},
    {"name": "码云", "url": GITEE_REPO}
]


async def _run_git_command(args, cwd=None, timeout=None):
    """异步运行git命令，返回CompletedProcess-like对象"""
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout = stdout.decode('utf-8', errors='replace')
        stderr = stderr.decode('utf-8', errors='replace')
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)
    
    class Result:
        pass
    result = Result()
    result.returncode = proc.returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class UpdateManager:
    """更新管理器类"""
    def __init__(self):
        """初始化更新管理器"""
        self.auto_update_enabled = False  # 默认关闭自动更新
        self.last_check_time = 0
        self.current_version = self._get_current_version()
        self.best_repo = None  # 最佳仓库地址
        self.repo_response_times = {}  # 仓库响应时间记录
        self._load_config()
        self._init_git_repo_task = None
        self._auto_check_task = None
        
    def start_async_tasks(self):
        """启动异步任务（需要在有事件循环的上下文中调用）"""
        if self._init_git_repo_task is None:
            try:
                self._init_git_repo_task = asyncio.get_event_loop().create_task(self._init_git_repository())
            except RuntimeError:
                # 没有运行中的事件循环，任务将在第一次异步调用时启动
                pass
        if self._auto_check_task is None:
            try:
                self._auto_check_task = asyncio.get_event_loop().create_task(self._auto_check_loop())
            except RuntimeError:
                pass
        # 异步获取git标签版本号（回退）
        try:
            asyncio.get_event_loop().create_task(self._async_get_current_version())
        except RuntimeError:
            pass
        
    async def _init_git_repository(self):
        """
        检查并初始化git仓库
        如果.git目录不存在，则初始化仓库并添加远程仓库
        """
        # 获取当前目录
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        git_dir = os.path.join(current_dir, '.git')
        
        # 检查.git目录是否存在
        if not os.path.isdir(git_dir):
            logger.info("[Update_Plugin] 检测到git仓库未初始化，开始初始化")
            try:
                # 初始化git仓库
                await _run_git_command(['git', 'init'], cwd=current_dir)
                logger.info("[Update_Plugin] git仓库初始化成功")
                
                # 选择最佳仓库地址
                selected_repo = await self._select_best_repo()
                
                # 检查是否有远程仓库
                try:
                    result = await _run_git_command(['git', 'remote', 'get-url', 'origin'], cwd=current_dir)
                    if not result.returncode == 0:
                        # 添加远程仓库
                        await _run_git_command(['git', 'remote', 'add', 'origin', selected_repo], cwd=current_dir)
                        logger.info(f"[Update_Plugin] 添加远程仓库成功: {selected_repo}")
                except Exception:
                    # 添加远程仓库
                    await _run_git_command(['git', 'remote', 'add', 'origin', selected_repo], cwd=current_dir)
                    logger.info(f"[Update_Plugin] 添加远程仓库成功: {selected_repo}")
                
                # 设置用户信息
                try:
                    await _run_git_command(['git', 'config', 'user.name', 'GracyBot'], cwd=current_dir)
                    await _run_git_command(['git', 'config', 'user.email', 'gracybot@example.com'], cwd=current_dir)
                    logger.info("[Update_Plugin] 设置git用户信息成功")
                except Exception as e:
                    logger.warning(f"[Update_Plugin] 设置git用户信息失败: {str(e)}")
                
            except Exception as e:
                logger.error(f"[Update_Plugin] 初始化git仓库失败: {str(e)}")
        else:
            logger.info("[Update_Plugin] git仓库已存在，跳过初始化")

    def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.auto_update_enabled = config.get('auto_update_enabled', False)
                    self.last_check_time = config.get('last_check_time', 0)
        except Exception as e:
            logger.error(f"[Update_Plugin] 加载配置失败: {str(e)}")

    def _save_config(self):
        """保存配置文件"""
        try:
            config = {
                'auto_update_enabled': self.auto_update_enabled,
                'last_check_time': self.last_check_time
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Update_Plugin] 保存配置失败: {str(e)}")

    def _get_current_version(self):
        """获取当前版本号（同步方式，仅尝试导入配置）"""
        try:
            # 从core/config.py获取版本号配置
            from core.config import BOT_VERSION
            version = BOT_VERSION
            # 移除可能的v前缀
            if version.startswith('v'):
                version = version[1:]
            return version
        except ImportError:
            return "1.0.0"  # 默认版本

    async def _async_get_current_version(self):
        """异步获取当前版本号（从git标签获取）"""
        try:
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            result = await _run_git_command(['git', 'describe', '--tags'], cwd=current_dir)
            if result.returncode == 0:
                version = result.stdout.strip()
                if version.startswith('v'):
                    version = version[1:]
                self.current_version = version
        except Exception:
            pass

    async def _test_single_repo(self, repo):
        """测试单个仓库连接（异步）"""
        try:
            start_time = time.time()
            result = await _run_git_command(
                ['git', 'ls-remote', '--tags', repo['url']],
                timeout=3
            )
            response_time = time.time() - start_time
            
            if result.returncode == 0:
                logger.info(f"[Update_Plugin] {repo['name']} 连接成功，响应时间: {response_time:.2f}秒")
                return repo, response_time, True
            else:
                logger.warning(f"[Update_Plugin] {repo['name']} 连接失败")
                return repo, None, False
        except Exception as e:
            logger.warning(f"[Update_Plugin] {repo['name']} 连接异常: {str(e)}")
            return repo, None, False

    async def _test_repo_connection_parallel(self):
        """并行测试仓库连接速度"""
        logger.info("[Update_Plugin] 开始并行测试仓库连接速度...")
        
        # 使用 asyncio.gather 并行测试所有仓库
        try:
            tasks = [self._test_single_repo(repo) for repo in REPO_LIST]
            results_list = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5)
        except Exception:
            logger.warning("[Update_Plugin] 并行测试超时，使用快速选择策略")
            return {}
        
        results = {}
        for item in results_list:
            if isinstance(item, Exception):
                continue
            repo, response_time, success = item
            results[repo['name']] = {
                'repo': repo,
                'response_time': response_time,
                'success': success
            }
        
        return results

    async def _select_best_repo(self):
        """选择最佳仓库地址（超快速切换版本）"""
        # 首先检查是否有缓存的最佳仓库且连接正常（极速检查）
        if self.best_repo:
            try:
                # 极速检查当前最佳仓库是否可用（0.5秒超时）
                result = await _run_git_command(
                    ['git', 'ls-remote', '--tags', self.best_repo['url']],
                    timeout=0.5
                )
                if result.returncode == 0:
                    logger.info(f"[Update_Plugin] 使用缓存的仓库: {self.best_repo['name']}")
                    return self.best_repo['url']
            except Exception:
                logger.warning(f"[Update_Plugin] 缓存仓库 {self.best_repo['name']} 连接失败，重新选择")
        
        logger.info("[Update_Plugin] 开始超快速仓库选择...")
        
        # 使用 asyncio.gather 同时测试两个仓库
        async def test_repo(name, url):
            try:
                start_time = time.time()
                result = await _run_git_command(
                    ['git', 'ls-remote', '--tags', url],
                    timeout=2
                )
                response_time = time.time() - start_time
                return name, url, result.returncode == 0, response_time
            except Exception:
                return name, url, False, None
        
        try:
            github_result, gitee_result = await asyncio.wait_for(
                asyncio.gather(
                    test_repo("GitHub", GITHUB_REPO),
                    test_repo("码云", GITEE_REPO),
                    return_exceptions=True
                ),
                timeout=2.5
            )
        except Exception:
            github_result = ("GitHub", GITHUB_REPO, False, None)
            gitee_result = ("码云", GITEE_REPO, False, None)
        
        results = {}
        for r in [github_result, gitee_result]:
            if isinstance(r, Exception):
                continue
            name, url, success, response_time = r
            results[name] = (success, response_time, url)
        
        # 检查结果并立即返回
        if results.get('GitHub') and results['GitHub'][0]:
            logger.info(f"[Update_Plugin] GitHub连接成功，响应时间: {results['GitHub'][1]:.2f}秒")
            self.best_repo = {"name": "GitHub", "url": GITHUB_REPO}
            self.repo_response_times['GitHub'] = results['GitHub'][1]
            return GITHUB_REPO
        
        if results.get('码云') and results['码云'][0]:
            logger.info(f"[Update_Plugin] 码云连接成功，响应时间: {results['码云'][1]:.2f}秒")
            self.best_repo = {"name": "码云", "url": GITEE_REPO}
            self.repo_response_times['码云'] = results['码云'][1]
            return GITEE_REPO
        
        # 如果都失败，使用快速串行重试（更短超时）
        logger.warning("[Update_Plugin] 并行测试失败，使用快速串行重试...")
        
        # 先快速测试码云（1秒超时）
        try:
            result = await _run_git_command(
                ['git', 'ls-remote', '--tags', GITEE_REPO],
                timeout=1
            )
            if result.returncode == 0:
                logger.info("[Update_Plugin] 码云快速重试成功")
                self.best_repo = {"name": "码云", "url": GITEE_REPO}
                return GITEE_REPO
        except Exception:
            pass
        
        # 再快速测试GitHub（1秒超时）
        try:
            result = await _run_git_command(
                ['git', 'ls-remote', '--tags', GITHUB_REPO],
                timeout=1
            )
            if result.returncode == 0:
                logger.info("[Update_Plugin] GitHub快速重试成功")
                self.best_repo = {"name": "GitHub", "url": GITHUB_REPO}
                return GITHUB_REPO
        except Exception:
            pass
        
        # 如果都失败，默认使用GitHub
        logger.error("[Update_Plugin] 所有仓库连接失败，默认使用GitHub")
        self.best_repo = {"name": "GitHub", "url": GITHUB_REPO}
        return GITHUB_REPO

    async def check_for_updates(self):
        """检查仓库更新"""
        try:
            # 选择最佳仓库地址
            selected_repo = await self._select_best_repo()
            logger.info(f"[Update_Plugin] 使用仓库: {self.best_repo['name']}")
            
            # 保存检查时间
            self.last_check_time = int(time.time())
            self._save_config()
            
            # 使用Git命令检查最新版本，增加超时时间和重试机制
            git_retry_count = 0
            max_git_retries = 2
            result = None
            
            while git_retry_count < max_git_retries:
                git_retry_count += 1
                try:
                    result = await _run_git_command(
                        ['git', 'ls-remote', '--tags', selected_repo],
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        break  # 成功则退出循环
                    else:
                        logger.warning(f"[Update_Plugin] 第{git_retry_count}次Git命令执行失败: {result.stderr}")
                        
                        if git_retry_count < max_git_retries:
                            wait_time = 5 * git_retry_count
                            logger.info(f"[Update_Plugin] {wait_time}秒后重试Git命令...")
                            await asyncio.sleep(wait_time)
                except subprocess.TimeoutExpired:
                    logger.warning(f"[Update_Plugin] 第{git_retry_count}次Git命令超时")
                    if git_retry_count < max_git_retries:
                        wait_time = 5 * git_retry_count
                        logger.info(f"[Update_Plugin] {wait_time}秒后重试Git命令...")
                        await asyncio.sleep(wait_time)
            
            if result is None or result.returncode != 0:
                logger.error(f"[Update_Plugin] Git命令最终执行失败")
                return None
            
            # 解析标签获取最新版本
            tags = []
            for line in result.stdout.strip().split('\n'):
                if 'refs/tags/' in line:
                    tag_part = line.split('refs/tags/')[-1]
                    # 移除可能的^{}后缀
                    if tag_part.endswith('^{}'):
                        tag_part = tag_part[:-3]
                    # 尝试解析版本号格式 vX.Y.Z 或 X.Y.Z
                    if tag_part.startswith('v'):
                        tag_part = tag_part[1:]
                    # 只处理数字版本号
                    if tag_part.replace('.', '').isdigit():
                        tags.append(tag_part)
            
            if not tags:
                logger.warning("[Update_Plugin] 未找到有效的版本标签")
                return None
            
            # 排序并获取最新版本
            tags.sort(key=lambda v: [int(x) for x in v.split('.')])
            latest_version = tags[-1]
            
            # 保存检查时间
            self.last_check_time = int(time.time())
            self._save_config()
            
            return {
                'latest_version': latest_version,
                'current_version': self.current_version,
                'need_update': self._compare_versions(latest_version, self.current_version)
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"[Update_Plugin] Git命令超时，可能是网络连接问题")
            # 保存检查时间
            self.last_check_time = int(time.time())
            self._save_config()
            return None
        except Exception as e:
                # 更友好的错误提示，避免直接暴露技术错误
                if 'Connection reset by peer' in str(e):
                    logger.error(f"[Update_Plugin] 检查更新失败: 网络连接被重置，请稍后再试")
                else:
                    logger.error(f"[Update_Plugin] 检查更新失败: {str(e)}")
                # 保存检查时间
                self.last_check_time = int(time.time())
                self._save_config()
                return None

    def _compare_versions(self, latest: str, current: str) -> bool:
        """比较版本号，判断是否需要更新"""
        try:
            # 清理版本号，移除v前缀
            if latest.startswith('v'):
                latest = latest[1:]
            if current.startswith('v'):
                current = current[1:]
            
            # 分割版本号为数字列表
            latest_parts = list(map(int, latest.split('.')))
            current_parts = list(map(int, current.split('.')))
            
            # 补齐长度
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts += [0] * (max_len - len(latest_parts))
            current_parts += [0] * (max_len - len(current_parts))
            
            # 比较每一部分
            for i in range(max_len):
                if latest_parts[i] > current_parts[i]:
                    return True
                elif latest_parts[i] < current_parts[i]:
                    return False
            
            return False  # 版本相同
        except Exception:
            return False

    async def perform_update(self):
        """执行更新操作"""
        try:
            # 更新前再次检查git仓库
            await self._init_git_repository()
            
            # 备份当前版本
            backup_dir = os.path.join('/tmp', f'gracybot_backup_{int(time.time())}')
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # 实际执行备份操作
            logger.info(f"[Update_Plugin] 开始备份当前版本到: {backup_dir}")
            try:
                import shutil
                shutil.copytree(current_dir, backup_dir, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
                logger.info(f"[Update_Plugin] 备份成功: {backup_dir}")
            except Exception as e:
                logger.warning(f"[Update_Plugin] 备份失败，但继续更新: {str(e)}")
            
            logger.info(f"[Update_Plugin] 开始执行更新，当前目录: {current_dir}")
            
            # 拉取最新代码
            result = await _run_git_command(
                ['git', 'pull', self.best_repo['url']],
                cwd=current_dir,
                timeout=120
            )
            
            if result.returncode == 0:
                logger.info(f"[Update_Plugin] 更新成功: {result.stdout}")
                return {'success': True, 'message': "更新成功喵~ Gracy已经变得更可爱啦~"}
            else:
                logger.error(f"[Update_Plugin] 更新失败: {result.stderr}")
                # 更新失败时尝试恢复备份
                try:
                    if os.path.exists(backup_dir):
                        logger.info(f"[Update_Plugin] 更新失败，尝试恢复备份: {backup_dir}")
                        # 删除当前目录内容（保留.git目录）
                        for item in os.listdir(current_dir):
                            if item != '.git':
                                item_path = os.path.join(current_dir, item)
                                if os.path.isfile(item_path):
                                    os.remove(item_path)
                                elif os.path.isdir(item_path):
                                    import shutil
                                    shutil.rmtree(item_path)
                        # 恢复备份
                        for item in os.listdir(backup_dir):
                            if item != '.git':
                                src_path = os.path.join(backup_dir, item)
                                dst_path = os.path.join(current_dir, item)
                                if os.path.isfile(src_path):
                                    import shutil
                                    shutil.copy2(src_path, dst_path)
                                elif os.path.isdir(src_path):
                                    import shutil
                                    shutil.copytree(src_path, dst_path)
                        logger.info("[Update_Plugin] 备份恢复成功")
                except Exception as restore_error:
                    logger.error(f"[Update_Plugin] 备份恢复失败: {str(restore_error)}")
                
                return {'success': False, 'message': f"更新失败喵，错误信息: {result.stderr}"}
                
        except Exception as e:
            logger.error(f"[Update_Plugin] 执行更新异常: {str(e)}")
            return {'success': False, 'message': f"更新过程中发生错误喵: {str(e)}"}

    def toggle_auto_update(self, enable: bool):
        """切换自动更新状态"""
        self.auto_update_enabled = enable
        self._save_config()
        return enable

    async def _auto_check_loop(self):
        """自动检查更新的循环协程"""
        while True:
            try:
                current_time = int(time.time())
                # 检查是否需要进行更新检测
                if current_time - self.last_check_time >= UPDATE_CHECK_INTERVAL:
                    await self._check_and_notify()
                
                # 每小时检查一次是否需要运行
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"[Update_Plugin] 自动检查协程异常: {str(e)}")
                await asyncio.sleep(3600)

    async def _check_and_notify(self):
        """检查更新并通知主人"""
        update_info = await self.check_for_updates()
        if update_info and update_info['need_update']:
            message = f"""🎁 发现新版本更新喵~
当前版本: {update_info['current_version']}
最新版本: {update_info['latest_version']}

请使用 /系统更新 命令进行更新哦~"""
            
            # 发送私信给主人
            try:
                await gracy_send_msg(str(MASTER_ID), GracyText(text=message), chat_type="private")
                logger.info(f"[Update_Plugin] 已通知主人有新版本可用")
            except Exception as e:
                logger.error(f"[Update_Plugin] 通知主人失败: {str(e)}")

    def _start_auto_check_task(self):
        """启动自动检查任务（兼容同步上下文）"""
        self.start_async_tasks()


# 全局更新管理器实例
update_manager = None


async def handle_update_plugin(self_bot, bot, message, user_id, chat_type, permission, logger):
    """
    处理更新插件的命令
    """
    global update_manager
    
    # 添加非常明显的日志标记
    logger.info("[Update_Plugin] ====== handle_update_plugin 函数被调用 ======")
    logger.info(f"[Update_Plugin] 用户ID: {user_id}, 消息类型: {chat_type}")
    
    try:
        if update_manager is None:
            logger.info("[Update_Plugin] 创建UpdateManager实例")
            update_manager = UpdateManager()
            update_manager.start_async_tasks()
        
        # 检查是否是主人
        if str(user_id) != str(MASTER_ID):
            logger.warning(f"[Update_Plugin] 用户 {user_id} 无权使用更新功能")
            await gracy_send_msg(str(user_id), GracyText(text="❌ 抱歉，只有主人才能使用此功能哦~"), chat_type=chat_type)
            return True
        
        # 获取消息内容
        message_content = message.get('text', '')
        logger.info(f"[Update_Plugin] 收到消息内容: {message_content}")
        
        # 处理 /系统更新 命令
        if message_content.startswith('/系统更新'):
            logger.info("[Update_Plugin] 开始处理 /系统更新 命令")
            
            # 发送检查中的提示
            await gracy_send_msg(str(user_id), GracyText(text="🔍 正在检查更新喵，请稍等..."), chat_type=chat_type)
            
            # 实际执行更新检查
            update_info = await update_manager.check_for_updates()
            
            if update_info is None:
                await gracy_send_msg(str(user_id), GracyText(text="❌ 检查更新失败喵，可能是网络问题，请稍后再试~"), chat_type=chat_type)
                return True
            
            if update_info['need_update']:
                # 询问是否执行更新
                message = f"🎁 发现新版本喵~\n当前版本: {update_info['current_version']}\n最新版本: {update_info['latest_version']}\n\n是否立即更新？回复 /确认更新 或 /取消更新"
                await gracy_send_msg(str(user_id), GracyText(text=message), chat_type=chat_type)
            else:
                await gracy_send_msg(str(user_id), GracyText(text=f"✅ 当前已是最新版本喵~\n版本号: {update_info['current_version']}"), chat_type=chat_type)
            
            return True
        # 处理 /开启自动更新 命令
        elif message_content.startswith('/开启自动更新'):
            logger.info("[Update_Plugin] 处理 /开启自动更新 命令")
            try:
                update_manager.toggle_auto_update(True)
                await gracy_send_msg(str(user_id), GracyText(text="✅ 已开启自动更新功能喵~"), chat_type=chat_type)
            except Exception as e:
                logger.error(f"[Update_Plugin] 开启自动更新失败: {str(e)}")
                await gracy_send_msg(str(user_id), GracyText(text="❌ 操作失败喵，请稍后再试~"), chat_type=chat_type)
            return True
        # 处理 /关闭自动更新 命令
        elif message_content.startswith('/关闭自动更新'):
            logger.info("[Update_Plugin] 处理 /关闭自动更新 命令")
            try:
                update_manager.toggle_auto_update(False)
                await gracy_send_msg(str(user_id), GracyText(text="✅ 已关闭自动更新功能喵~"), chat_type=chat_type)
            except Exception as e:
                logger.error(f"[Update_Plugin] 关闭自动更新失败: {str(e)}")
                await gracy_send_msg(str(user_id), GracyText(text="❌ 操作失败喵，请稍后再试~"), chat_type=chat_type)
            return True
        
        # 处理 /确认更新 命令
        elif message_content.startswith('/确认更新'):
            logger.info("[Update_Plugin] 处理 /确认更新 命令")
            
            # 发送更新中的提示
            await gracy_send_msg(str(user_id), GracyText(text="🔄 开始执行更新喵，请耐心等待..."), chat_type=chat_type)
            
            # 执行更新操作
            update_result = await update_manager.perform_update()
            
            if update_result['success']:
                await gracy_send_msg(str(user_id), GracyText(text=update_result['message']), chat_type=chat_type)
            else:
                await gracy_send_msg(str(user_id), GracyText(text=update_result['message']), chat_type=chat_type)
            
            return True
        
        # 处理 /取消更新 命令
        elif message_content.startswith('/取消更新'):
            logger.info("[Update_Plugin] 处理 /取消更新 命令")
            await gracy_send_msg(str(user_id), GracyText(text="✅ 已取消更新操作喵~"), chat_type=chat_type)
            return True
        
        logger.info("[Update_Plugin] 未匹配到任何更新相关命令")
        # 默认返回False表示未处理
        return False
    except Exception as e:
        # 捕获所有异常，确保返回友好的错误提示
        logger.error(f"[Update_Plugin] 处理更新命令时发生异常: {str(e)}")
        await gracy_send_msg(str(user_id), GracyText(text="❌ 检查更新失败喵，请稍后再试~"), chat_type=chat_type)
        return True


# 插件初始化
# logger.info("✅ 更新插件加载完成") # 注释掉，避免重复记录

# 导出处理函数
export_dict = {
    'handle_update_plugin': handle_update_plugin
}

# 模块初始化时的日志
logger.info("[Update_Plugin] ====== 更新插件初始化完成 ======")
def __init__():
    logger.info("[Update_Plugin] ====== 更新插件__init__被调用 ======")

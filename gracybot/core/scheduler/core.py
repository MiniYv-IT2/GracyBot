"""GracyBot 定时调度器 — 支持 interval / delayed / cron

用法:
    from gracybot.core.scheduler import scheduler

    scheduler.add_interval("ping", my_callback, 300)
    scheduler.add_cron("daily", my_callback, "0 6 * * *")
    scheduler.start()
    ...
    scheduler.stop()
"""

import asyncio
import datetime
import logging
from typing import Any, Callable, Coroutine, Optional

from .cron import parse_cron, match_cron

_logger = logging.getLogger("Core.Scheduler")

TaskCallback = Callable[..., Any] | Callable[..., Coroutine[Any, Any, None]]


class ScheduledTask:
    __slots__ = (
        "name", "callback", "args", "kwargs",
        "kind", "interval", "cron_parsed",
        "_task", "_running",
    )

    def __init__(
        self,
        name: str,
        callback: TaskCallback,
        kind: str,
        args: tuple = (),
        kwargs: dict | None = None,
        interval: float = 0,
        cron_parsed: dict | None = None,
    ):
        self.name = name
        self.callback = callback
        self.args = args
        self.kwargs = kwargs or {}
        self.kind = kind
        self.interval = interval
        self.cron_parsed = cron_parsed
        self._task: asyncio.Task | None = None
        self._running = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "interval": self.interval,
            "running": self._running,
        }


class Scheduler:
    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False

    # ── 生命周期 ──

    def start(self):
        if self._running:
            return
        self._running = True
        for task in self._tasks.values():
            self._schedule_task(task)
        _logger.info(f"调度器已启动，{len(self._tasks)} 个任务")

    def stop(self):
        self._running = False
        count = 0
        for task in self._tasks.values():
            if task._task and not task._task.done():
                task._task.cancel()
                count += 1
        self._tasks.clear()
        if count:
            _logger.info(f"调度器已停止，已取消 {count} 个任务")

    # ── 注册 ──

    def add_interval(
        self,
        name: str,
        callback: TaskCallback,
        seconds: float,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> bool:
        if name in self._tasks:
            _logger.warning(f"定时任务 {name} 已存在")
            return False
        task = ScheduledTask(name, callback, "interval", args, kwargs, interval=seconds)
        self._tasks[name] = task
        if self._running:
            self._schedule_task(task)
        _logger.info(f"新增 interval 任务: {name} ({seconds}s)")
        return True

    def add_delayed(
        self,
        name: str,
        callback: TaskCallback,
        seconds: float,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> bool:
        if name in self._tasks:
            _logger.warning(f"定时任务 {name} 已存在")
            return False
        task = ScheduledTask(name, callback, "delayed", args, kwargs, interval=seconds)
        self._tasks[name] = task
        if self._running:
            self._schedule_task(task)
        _logger.info(f"新增 delayed 任务: {name} ({seconds}s)")
        return True

    def add_cron(
        self,
        name: str,
        callback: TaskCallback,
        spec: str,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> bool:
        if name in self._tasks:
            _logger.warning(f"定时任务 {name} 已存在")
            return False
        parsed = parse_cron(spec)
        if parsed is None:
            _logger.error(f"cron 表达式无效: {spec}")
            return False
        task = ScheduledTask(name, callback, "cron", args, kwargs, cron_parsed=parsed)
        self._tasks[name] = task
        if self._running:
            self._schedule_task(task)
        _logger.info(f"新增 cron 任务: {name} ({spec})")
        return True

    def remove(self, name: str) -> bool:
        task = self._tasks.pop(name, None)
        if task is None:
            return False
        if task._task and not task._task.done():
            task._task.cancel()
        _logger.info(f"移除定时任务: {name}")
        return True

    def get(self, name: str) -> dict | None:
        task = self._tasks.get(name)
        return task.to_dict() if task else None

    def list(self) -> list[dict]:
        return [t.to_dict() for t in self._tasks.values()]

    def clear(self) -> int:
        count = len(self._tasks)
        for task in list(self._tasks.values()):
            if task._task and not task._task.done():
                task._task.cancel()
        self._tasks.clear()
        if count:
            _logger.info(f"清空所有定时任务，共 {count} 个")
        return count

    # ── 内部调度 ──

    def _schedule_task(self, task: ScheduledTask):
        if not self._running:
            return
        if task._task and not task._task.done():
            return
        if task.kind == "interval":
            task._task = asyncio.create_task(
                self._run_interval(task), name=f"sched:{task.name}"
            )
        elif task.kind == "delayed":
            task._task = asyncio.create_task(
                self._run_delayed(task), name=f"sched:{task.name}"
            )
        elif task.kind == "cron":
            task._task = asyncio.create_task(
                self._run_cron(task), name=f"sched:{task.name}"
            )

    async def _run_interval(self, task: ScheduledTask):
        task._running = True
        try:
            while self._running and task.name in self._tasks:
                await asyncio.sleep(task.interval)
                if not self._running or task.name not in self._tasks:
                    break
                await self._call_safe(task)
        except asyncio.CancelledError:
            pass
        finally:
            task._running = False

    async def _run_delayed(self, task: ScheduledTask):
        task._running = True
        try:
            await asyncio.sleep(task.interval)
            if self._running and task.name in self._tasks:
                await self._call_safe(task)
        except asyncio.CancelledError:
            pass
        finally:
            task._running = False
            self._tasks.pop(task.name, None)

    async def _run_cron(self, task: ScheduledTask):
        task._running = True
        try:
            last_check = None
            while self._running and task.name in self._tasks:
                now = datetime.datetime.now()
                check_key = (now.minute, now.hour, now.day, now.month)
                if check_key != last_check and match_cron(task.cron_parsed, now):
                    last_check = check_key
                    await self._call_safe(task)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
        finally:
            task._running = False

    async def _call_safe(self, task: ScheduledTask):
        try:
            result = task.callback(*task.args, **task.kwargs)
            if result is not None and hasattr(result, "__await__"):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _logger.error(
                f"定时任务 {task.name} 执行异常: {type(e).__name__}: {e}",
                exc_info=True,
            )


scheduler = Scheduler()

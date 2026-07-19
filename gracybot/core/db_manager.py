import os
import re
import asyncio
from typing import Optional, List
import aiosqlite

_db_instances: dict = {}
_db_instances_lock = asyncio.Lock()


def _sanitize(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff\-]', '_', name)


class DBHandle:
    def __init__(self, plugin_name: str, db_path: str):
        self._name = plugin_name
        self._path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def _ensure(self):
        if self._conn is None:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            self._conn = await aiosqlite.connect(self._path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")

    async def execute(self, sql: str, *params) -> int:
        async with self._lock:
            await self._ensure()
            cursor = await self._conn.execute(sql, params or ())
            await self._conn.commit()
            return cursor.lastrowid

    async def executemany(self, sql: str, params_list: List[tuple]) -> None:
        async with self._lock:
            await self._ensure()
            await self._conn.executemany(sql, params_list)
            await self._conn.commit()

    async def fetchall(self, sql: str, *params) -> list:
        async with self._lock:
            await self._ensure()
            cursor = await self._conn.execute(sql, params or ())
            return await cursor.fetchall()

    async def fetchone(self, sql: str, *params):
        async with self._lock:
            await self._ensure()
            cursor = await self._conn.execute(sql, params or ())
            return await cursor.fetchone()

    async def close(self):
        async with self._lock:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None


async def get_db(plugin_name: str) -> DBHandle:
    safe = _sanitize(plugin_name)
    if not safe:
        safe = "unnamed"
    from gracybot.core.tools.paths import get_db_path
    path = get_db_path(safe)

    async with _db_instances_lock:
        if path not in _db_instances:
            _db_instances[path] = DBHandle(plugin_name, path)
        return _db_instances[path]


async def close_all():
    async with _db_instances_lock:
        for handle in _db_instances.values():
            await handle.close()
        _db_instances.clear()

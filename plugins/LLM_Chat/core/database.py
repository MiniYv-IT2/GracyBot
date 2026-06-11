import aiosqlite
import json
import os
import asyncio
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "conversations.db")

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                chat_id TEXT PRIMARY KEY,
                current_persona TEXT DEFAULT '默认人设',
                max_context INTEGER DEFAULT 50
            )
        """)
        
        await cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                task_time TEXT NOT NULL,
                task_content TEXT NOT NULL,
                persona TEXT,
                enabled INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.commit()

async def add_message(chat_id, role, content):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("INSERT INTO conversations (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, role, content))
        await conn.commit()

async def get_messages(chat_id, limit=50):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT role, content FROM conversations WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (chat_id, limit))
        messages = await cursor.fetchall()
    return [{"role": role, "content": content} for role, content in reversed(messages)]

async def clear_messages(chat_id):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
        await conn.commit()

async def add_persona(name, content):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        try:
            await cursor.execute("INSERT INTO personas (name, content) VALUES (?, ?)", (name, content))
            await conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def delete_persona(name):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("DELETE FROM personas WHERE name = ?", (name,))
        await conn.commit()

async def get_personas():
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT name, content FROM personas")
        personas = {name: content for name, content in await cursor.fetchall()}
    return personas

async def get_persona(name):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT content FROM personas WHERE name = ?", (name,))
        result = await cursor.fetchone()
    return result[0] if result else None

async def set_current_persona(chat_id, persona):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("INSERT OR REPLACE INTO settings (chat_id, current_persona) VALUES (?, ?)", (chat_id, persona))
        await conn.commit()

async def get_current_persona(chat_id):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT current_persona FROM settings WHERE chat_id = ?", (chat_id,))
        result = await cursor.fetchone()
    return result[0] if result else "默认人设"

async def set_max_context(chat_id, max_context):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("INSERT OR REPLACE INTO settings (chat_id, max_context) VALUES (?, ?)", (chat_id, max_context))
        await conn.commit()

async def get_max_context(chat_id):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT max_context FROM settings WHERE chat_id = ?", (chat_id,))
        result = await cursor.fetchone()
    return result[0] if result else 50

async def add_scheduled_task(chat_id, task_time, task_content, persona=None):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("INSERT INTO scheduled_tasks (chat_id, task_time, task_content, persona) VALUES (?, ?, ?, ?)", 
                       (chat_id, task_time, task_content, persona))
        await conn.commit()

async def get_scheduled_tasks():
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("SELECT id, chat_id, task_time, task_content, persona FROM scheduled_tasks WHERE enabled = 1")
        tasks = await cursor.fetchall()
    return tasks

async def disable_task(task_id):
    await ensure_db_initialized()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.cursor()
        await cursor.execute("UPDATE scheduled_tasks SET enabled = 0 WHERE id = ?", (task_id,))
        await conn.commit()

# 惰性初始化：首次使用时才连接数据库
_init_lock = asyncio.Lock()
_init_done = False

async def ensure_db_initialized():
    global _init_done
    if _init_done:
        return
    async with _init_lock:
        if not _init_done:
            await init_db()
            _init_done = True

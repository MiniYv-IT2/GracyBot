import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "conversations.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id TEXT PRIMARY KEY,
            current_persona TEXT DEFAULT '默认人设',
            max_context INTEGER DEFAULT 50
        )
    """)
    
    cursor.execute("""
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
    
    conn.commit()
    conn.close()

def add_message(chat_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, role, content))
    conn.commit()
    conn.close()

def get_messages(chat_id, limit=50):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM conversations WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (chat_id, limit))
    messages = cursor.fetchall()
    conn.close()
    return [{"role": role, "content": content} for role, content in reversed(messages)]

def clear_messages(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def add_persona(name, content):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO personas (name, content) VALUES (?, ?)", (name, content))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_persona(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM personas WHERE name = ?", (name,))
    conn.commit()
    conn.close()

def get_personas():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, content FROM personas")
    personas = {name: content for name, content in cursor.fetchall()}
    conn.close()
    return personas

def get_persona(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM personas WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_current_persona(chat_id, persona):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (chat_id, current_persona) VALUES (?, ?)", (chat_id, persona))
    conn.commit()
    conn.close()

def get_current_persona(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT current_persona FROM settings WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "默认人设"

def set_max_context(chat_id, max_context):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (chat_id, max_context) VALUES (?, ?)", (chat_id, max_context))
    conn.commit()
    conn.close()

def get_max_context(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT max_context FROM settings WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 50

def add_scheduled_task(chat_id, task_time, task_content, persona=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO scheduled_tasks (chat_id, task_time, task_content, persona) VALUES (?, ?, ?, ?)", 
                   (chat_id, task_time, task_content, persona))
    conn.commit()
    conn.close()

def get_scheduled_tasks():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, chat_id, task_time, task_content, persona FROM scheduled_tasks WHERE enabled = 1")
    tasks = cursor.fetchall()
    conn.close()
    return tasks

def disable_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE scheduled_tasks SET enabled = 0 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

init_db()

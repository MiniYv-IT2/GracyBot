"""Scan specific files for log message format violations."""
import os, re

BASE = r"E:\ai智能体\gracybot"

# Files with potential violations (from previous scan results)
TARGETS = [
    # New files found
    "core/gracy_adapter/pool.py",
    "plugins/GracyUI_plugin/GracyUI_plugin.py",
    # Previously found
    "core/security_manager.py",
    "plugins/SysInfo_plugin/SysInfo_plugin.py",
]

def scan(filepath):
    full = os.path.join(BASE, filepath)
    if not os.path.exists(full):
        print(f"  [NOT FOUND] {filepath}")
        return
    
    with open(full, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find logger name
    logger_name = None
    for line in lines:
        m = re.search(r'(?:logger|_logger)\s*=\s*(?:logging\.getLogger|logger_manager\.get_logger)\(["\']([^"\']+)["\']\)', line)
        if m:
            logger_name = m.group(1)
            break
    
    # Find all log calls whose message starts with [...]
    violations = []
    for i, line in enumerate(lines, 1):
        m = re.search(r'(logger|_logger)\.(info|debug|warning|error|critical)\(.*?\)', line)
        if not m:
            continue
        # Extract the message content (first string argument)
        msg_match = re.search(r'\.(info|debug|warning|error|critical)\(\s*(?:f)?(["\'])((?:[^"\'\\]|\\.)*?)\2', line)
        if not msg_match:
            continue
        msg = msg_match.group(3)
        if msg.startswith('['):
            violations.append((i, msg, line.strip()))
    
    if violations:
        print(f"\n--- {filepath} ---")
        print(f"  Logger: {logger_name}")
        for lineno, msg, raw in violations:
            print(f"  L{lineno}: {raw[:120]}")

for f in TARGETS:
    scan(f)

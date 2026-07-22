import os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files to check: new files from git diff gitee/allnew HEAD (not in earlier audit)
FILES = [
    "core/gracy_adapter/pool.py",
    "core/gracy_adapter/qq_official/auth.py",
    "core/main.py",
    "core/plugin_manager.py",
    "plugins/Easysearch/Easysearch.py",
    "plugins/Easysearch/main.py",
    "plugins/ExamplePlugin/ExamplePlugin.py",
    "plugins/Gracone_Plugin/bridge/api_bridge.py",
    "plugins/Gracone_Plugin/bridge/event_translator.py",
    "plugins/Gracone_Plugin/bridge/matcher_bridge.py",
    "plugins/Gracone_Plugin/gracone_admin.py",
    "plugins/Gracone_Plugin/gracone_core.py",
    "plugins/Gracone_Plugin/gracone_ext_plugins.py",
    "plugins/GracyUI_plugin/GracyUI_plugin.py",
    "plugins/GracyUI_plugin/backend/app.py",
    "plugins/GracyUI_plugin/backend/routes/auth.py",
    "plugins/GracyUI_plugin/backend/routes/bot.py",
    "plugins/GracyUI_plugin/backend/routes/dashboard.py",
    "plugins/GracyUI_plugin/backend/routes/logs.py",
    "plugins/Help_plugin/Help_plugin.py",
    "plugins/LLM_Chat/LLM_Chat.py",
    "plugins/LLM_Chat/core/api_handler.py",
    "plugins/LLM_Chat/core/event_handler.py",
    "plugins/LLM_Chat/core/scheduler.py",
    "plugins/MonitorPlugin/MonitorPlugin.py",
    "plugins/Music_Plugin/Music_Plugin.py",
    "plugins/Music_Plugin/core/api.py",
    "plugins/Music_Plugin/core/draw.py",
    "plugins/NTE_Guide_Plugin/NTE_Guide_Plugin.py",
    "plugins/Screenshot/main.py",
    "plugins/SysInfo_plugin/core/napcat_api.py",
    "plugins/Update_Plugin/Update_Plugin.py",
    "plugins/Xiaoyu_plugin/core/draw.py",
]

# Also check previously-audited files that had violations
PREVIOUS_VIOLATIONS = [
    "core/security_manager.py",
    "plugins/SysInfo_plugin/SysInfo_plugin.py",
]

PAT_LOGGER = re.compile(r'(?:logger|_logger)\s*=\s*(?:logging\.getLogger|logger_manager\.get_logger)\(["\']([^"\']+)["\']\)')
PAT_LOG_CALL = re.compile(r'(logger|_logger)\.(info|debug|warning|error|critical)\(.*\)')

def get_logger_name(filepath):
    """Extract the logger name from a file."""
    full = os.path.join(BASE, filepath)
    if not os.path.exists(full):
        return None, None
    with open(full, 'r', encoding='utf-8') as f:
        for line in f:
            m = PAT_LOGGER.search(line)
            if m:
                return m.group(1), m.group(1).split('.')[-1]
    return None, None

def check_file(filepath):
    """Check for log message violations in a file."""
    full = os.path.join(BASE, filepath)
    if not os.path.exists(full):
        return None
    logger_name, module_part = get_logger_name(filepath)
    if not logger_name:
        return None
    
    violations = []
    with open(full, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        # Match log calls with string content
        m = PAT_LOG_CALL.search(line)
        if not m:
            continue
        # Check if message starts with [ModuleName] pattern
        stripped = line.strip()
        # Check for pattern like logger.info("[ModuleName] ...")
        if module_part:
            pat = re.compile(rf'\.(info|debug|warning|error|critical)\(\s*f?\["{re.escape(module_part)}\]')
            if pat.search(stripped):
                violations.append((i, stripped, logger_name, module_part))
    
    return violations

def check_file_raw(filepath):
    """Alternative: show every log call line with its line number."""
    full = os.path.join(BASE, filepath)
    if not os.path.exists(full):
        return []
    results = []
    with open(full, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'(logger|_logger)\.(info|debug|warning|error|critical)\(', stripped):
            # Check for [xxx] prefix at start of message
            msg_match = re.search(r'\(["\'](\[?\w+\]?)', stripped)
            if msg_match:
                prefix = msg_match.group(1)
                results.append((i, prefix, stripped))
    return results

# Scan new files
print("=" * 70)
print("新文件日志格式扫描（相对于远程 allnew 分支）")
print("=" * 70)

for f in FILES:
    logger_name, module_part = get_logger_name(f)
    if not logger_name:
        print(f"\n--- {f} ---")
        print("  [无 Logger 定义]")
        continue
    raw = check_file_raw(f)
    if not raw:
        continue
    for lineno, prefix, line in raw:
        # Check if prefix is [ModuleName] pattern (redundant)
        if module_part and prefix == f"[{module_part}]":
            print(f"\n  ** 违规 ** {f}:{lineno}")
            print(f"     Logger: {logger_name}")
            print(f"     消息: {line[:100]}")
        elif prefix.startswith('['):
            print(f"\n  ? 注意 {f}:{lineno} — 消息以 {prefix} 开头")
            print(f"     Logger: {logger_name}")
            print(f"     消息: {line[:100]}")

print("\n" + "=" * 70)
print("之前已查出违规的旧文件")
print("=" * 70)
for f in PREVIOUS_VIOLATIONS:
    raw = check_file_raw(f)
    logger_name, module_part = get_logger_name(f)
    for lineno, prefix, line in raw:
        if module_part and prefix == f"[{module_part}]":
            print(f"\n  ** 违规 ** {f}:{lineno}")
            print(f"     Logger: {logger_name}")
            print(f"     消息: {line[:100]}")

print("\nDone.")

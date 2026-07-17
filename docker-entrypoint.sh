#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════
# GracyBot Docker Entrypoint
# ═══════════════════════════════════════════════════════════

# 挂载自定义插件：plugins_custom/ → gracybot/plugins_custom/
if [ -d /gracybot/plugins_custom ] && [ "$(ls -A /gracybot/plugins_custom 2>/dev/null)" ]; then
    ln -sfn /gracybot/plugins_custom /gracybot/gracybot/plugins_custom
fi

# 首次运行：storage/ 目录由 VOLUME 保证存在
# storage/config.json 由 gracy run 首次启动时自动创建
# 但实例需要用户主动创建

exec "$@"

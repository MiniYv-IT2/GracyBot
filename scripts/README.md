# GracyBot 脚本清单

| 脚本 | 用途 |
|------|------|
| `strip_py_comments.py` | 基于 Python tokenize 精准去除 `#` 注释和 `"""` docstring，保留代码字符串参数 |
| `generate_plugin.py` | 10 层架构插件模板生成器，按新风格目录结构创建插件骨架 |
| `debug_satori.py` | Satori 适配器调试脚本，校验语法和连接 |
| `test_fake_event.py` | 伪造事件塞入 pipeline，测试机器人响应 |
| `test_group_at.py` | 测试群聊 AT 机器人的消息接收和响应 |
| `test_self_send.py` | 测试机器人自收自发的消息处理 |
| `_check_logs.py` | 扫描指定文件的日志格式合规性（首次审计） |
| `_check_logs2.py` | 扫描指定文件的日志格式合规性（二次审计） |

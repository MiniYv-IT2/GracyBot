import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { LogStoreState, LogEntry, LogLevel } from '../types';
import { saveAs } from 'file-saver';
import dayjs from 'dayjs';

const mockLogs: LogEntry[] = [
  {
    id: 'log-1',
    timestamp: Date.now() - 300000,
    level: 'info',
    message: '系统启动成功，版本 v2.5.0',
  },
  {
    id: 'log-2',
    timestamp: Date.now() - 240000,
    level: 'info',
    message: '适配器 WebSocket 连接成功',
  },
  {
    id: 'log-3',
    timestamp: Date.now() - 180000,
    level: 'warn',
    message: 'API 响应时间超过阈值 (2.5s)',
  },
  {
    id: 'log-4',
    timestamp: Date.now() - 120000,
    level: 'info',
    message: '好友数量同步成功：42人',
  },
  {
    id: 'log-5',
    timestamp: Date.now() - 60000,
    level: 'error',
    message: '插件加载失败：语音合成 v1.5.3',
  },
];

export const useLogStore = create<LogStoreState>()(
  persist(
    (set, get) => ({
      logs: mockLogs,
      filterLevel: 'all',

      addLog: (level: LogLevel, message: string) => {
        const newLog: LogEntry = {
          id: 'log-' + Date.now(),
          timestamp: Date.now(),
          level,
          message,
        };
        set((state) => ({
          logs: [newLog, ...state.logs].slice(0, 50), // 最多保留50条
        }));
      },

      clearLogs: () => {
        set({ logs: [] });
      },

      setFilterLevel: (level: LogLevel | 'all') => {
        set({ filterLevel: level });
      },

      exportLogs: () => {
        const logs = get().logs;
        const text = logs
          .map(log => `[${dayjs(log.timestamp).format('YYYY-MM-DD HH:mm:ss')}] [${log.level.toUpperCase()}] ${log.message}`)
          .join('\n');
        const blob = new Blob([text], { type: 'text/plain' });
        saveAs(blob, `logs_${dayjs().format('YYYYMMDD_HHmmss')}.txt`);
      },

      simulateLog: () => {
        const levels: LogLevel[] = ['info', 'warn', 'error'];
        const messages = [
          '收到新消息：用户 123456',
          '会话超时，自动清理',
          '内存使用率超过80%',
          '人物卡切换成功：小樱猫娘',
          '定时任务执行：每日问候',
          'API 请求频率限制警告',
          '插件更新可用：智能回复增强 v1.3.0',
        ];
        const level = levels[Math.floor(Math.random() * levels.length)];
        const message = messages[Math.floor(Math.random() * messages.length)];
        get().addLog(level, message);
      },
    }),
    {
      name: 'ai-bot-logs',
    }
  )
);

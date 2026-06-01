import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { PluginStoreState, Plugin } from '../types';

const mockPlugins: Plugin[] = [
  {
    id: 'plugin-1',
    name: '智能回复增强',
    description: '提升Bot的回复质量和上下文理解能力',
    version: '1.2.0',
    author: '灵羽工作室',
    icon: '🤖',
    enabled: false,
    installed: false,
  },
  {
    id: 'plugin-2',
    name: '图片识别助手',
    description: '支持图片内容识别和描述生成',
    version: '2.0.1',
    author: 'AI实验室',
    icon: '🖼️',
    enabled: false,
    installed: false,
  },
  {
    id: 'plugin-3',
    name: '语音合成',
    description: '将文本转换为自然流畅的语音',
    version: '1.5.3',
    author: '语音科技',
    icon: '🔊',
    enabled: false,
    installed: false,
  },
  {
    id: 'plugin-4',
    name: '定时任务',
    description: '设置定时发送消息和提醒功能',
    version: '1.0.0',
    author: '效率工具组',
    icon: '⏰',
    enabled: false,
    installed: false,
  },
  {
    id: 'plugin-5',
    name: '数据统计面板',
    description: '可视化展示Bot使用统计数据',
    version: '1.3.2',
    author: '数据分析团队',
    icon: '📊',
    enabled: false,
    installed: false,
  },
];

export const usePluginStore = create<PluginStoreState>()(
  persist(
    (set) => ({
      installedPlugins: [],
      availablePlugins: mockPlugins,

      installPlugin: (pluginId: string) => {
        set((state) => {
          const plugin = state.availablePlugins.find(p => p.id === pluginId);
          if (!plugin) return state;

          const updatedPlugin = { ...plugin, installed: true, enabled: true };
          return {
            installedPlugins: [...state.installedPlugins, updatedPlugin],
            availablePlugins: state.availablePlugins.map(p =>
              p.id === pluginId ? updatedPlugin : p
            ),
          };
        });
      },

      uninstallPlugin: (pluginId: string) => {
        set((state) => ({
          installedPlugins: state.installedPlugins.filter(p => p.id !== pluginId),
          availablePlugins: state.availablePlugins.map(p =>
            p.id === pluginId ? { ...p, installed: false, enabled: false } : p
          ),
        }));
      },

      togglePlugin: (pluginId: string, enabled: boolean) => {
        set((state) => ({
          installedPlugins: state.installedPlugins.map(p =>
            p.id === pluginId ? { ...p, enabled } : p
          ),
          availablePlugins: state.availablePlugins.map(p =>
            p.id === pluginId ? { ...p, enabled } : p
          ),
        }));
      },

      fetchPlugins: () => {
        // 模拟从商店获取插件列表
      },
    }),
    {
      name: 'ai-bot-plugins',
    }
  )
);

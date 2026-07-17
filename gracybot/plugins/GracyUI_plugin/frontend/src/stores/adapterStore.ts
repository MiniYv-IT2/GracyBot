import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AdapterState } from '../types';

export const useAdapterStore = create<AdapterState>()(
  persist(
    (set) => ({
      status: 'disconnected',
      wsUrl: 'ws://127.0.0.1:6700',
      accessToken: '',
      protocol: 'ws',
      autoReconnect: true,

      connect: () => {
        set({ status: 'connecting' });
        // 模拟连接过程
        setTimeout(() => {
          set({ status: 'connected' });
        }, 1500);
      },

      disconnect: () => {
        set({ status: 'disconnected' });
      },

      testConnection: () => {
        set({ status: 'connecting' });
        setTimeout(() => {
          set({ status: 'connected' });
        }, 1000);
      },

      updateConfig: (config) => {
        set(config);
      },
    }),
    {
      name: 'ai-bot-adapter',
    }
  )
);
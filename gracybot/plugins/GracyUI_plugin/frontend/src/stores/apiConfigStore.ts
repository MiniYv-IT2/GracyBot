import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ApiConfigState } from '../types';

export const useApiConfigStore = create<ApiConfigState>()(
  persist(
    (_set) => ({
      provider: 'openai',
      apiKey: '',
      baseUrl: 'https://api.openai.com/v1',
      model: 'gpt-3.5-turbo',

      testConnection: async () => {
        // 模拟API测试连接
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve(true);
          }, 1000);
        });
      },

      saveConfig: () => {
        // 配置会自动保存到localStorage
      },
    }),
    {
      name: 'ai-bot-api-config',
    }
  )
);

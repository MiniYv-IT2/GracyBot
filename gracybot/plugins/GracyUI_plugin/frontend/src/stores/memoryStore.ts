import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MemoryStoreState, Memory } from '../types';
import { saveAs } from 'file-saver';

export const useMemoryStore = create<MemoryStoreState>()(
  persist(
    (set, get) => ({
      globalMemories: [
        { id: 'mem-1', key: '用户偏好', value: '喜欢猫娘风格', createdAt: Date.now() },
        { id: 'mem-2', key: '语言习惯', value: '使用轻松活泼的语气', createdAt: Date.now() - 86400000 },
      ],
      sessionMemories: {},
      similarityThreshold: 0.7,

      addGlobalMemory: (key: string, value: string) => {
        const newMemory: Memory = {
          id: 'mem-' + Date.now(),
          key,
          value,
          createdAt: Date.now(),
        };
        set((state) => ({
          globalMemories: [...state.globalMemories, newMemory],
        }));
      },

      deleteGlobalMemory: (id: string) => {
        set((state) => ({
          globalMemories: state.globalMemories.filter(m => m.id !== id),
        }));
      },

      addSessionMemory: (sessionId: string, key: string, value: string) => {
        const newMemory: Memory = {
          id: 'mem-' + Date.now(),
          key,
          value,
          createdAt: Date.now(),
        };
        set((state) => ({
          sessionMemories: {
            ...state.sessionMemories,
            [sessionId]: [...(state.sessionMemories[sessionId] || []), newMemory],
          },
        }));
      },

      clearSessionMemories: (sessionId: string) => {
        set((state) => {
          const newSessionMemories = { ...state.sessionMemories };
          delete newSessionMemories[sessionId];
          return { sessionMemories: newSessionMemories };
        });
      },

      setSimilarityThreshold: (threshold: number) => {
        set({ similarityThreshold: threshold });
      },

      exportMemories: () => {
        const data = {
          global: get().globalMemories,
          session: get().sessionMemories,
        };
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        saveAs(blob, 'memories.json');
      },

      importMemories: (json: string) => {
        try {
          const data = JSON.parse(json);
          set({
            globalMemories: data.global || [],
            sessionMemories: data.session || {},
          });
        } catch (error) {
          console.error('导入失败:', error);
        }
      },
    }),
    {
      name: 'ai-bot-memories',
    }
  )
);

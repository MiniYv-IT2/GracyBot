import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { HyperParamsState, ParamPreset } from '../types';

const presets: Record<ParamPreset, Omit<HyperParamsState, 'preset' | 'applyPreset' | 'resetToDefault' | 'updateParam'>> = {
  creative: {
    temperature: 0.9,
    topP: 0.95,
    presencePenalty: 0.6,
    frequencyPenalty: 0.3,
    maxTokens: 2048,
  },
  balanced: {
    temperature: 0.7,
    topP: 0.9,
    presencePenalty: 0.0,
    frequencyPenalty: 0.0,
    maxTokens: 1024,
  },
  precise: {
    temperature: 0.3,
    topP: 0.7,
    presencePenalty: 0.0,
    frequencyPenalty: 0.2,
    maxTokens: 512,
  },
};

export const useHyperParamsStore = create<HyperParamsState>()(
  persist(
    (set) => ({
      temperature: 0.7,
      topP: 0.9,
      presencePenalty: 0.0,
      frequencyPenalty: 0.0,
      maxTokens: 1024,
      preset: 'balanced',

      applyPreset: (preset: ParamPreset) => {
        set({ ...presets[preset], preset });
      },

      resetToDefault: () => {
        set(presets.balanced);
        set({ preset: 'balanced' });
      },

      updateParam: (key: keyof HyperParamsState, value: number) => {
        set({ [key]: value } as Partial<HyperParamsState>);
      },
    }),
    {
      name: 'ai-bot-hyperparams',
    }
  )
);

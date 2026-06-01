import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { DashboardState } from '../types';

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set) => ({
      friendCount: 0,
      groupCount: 0,
      systemVersion: '',
      lastUpdate: Date.now(),
      loading: false,

      fetchStats: async () => {
        set({ loading: true });
        try {
          const res = await fetch('/api/dashboard/stats');
          const data = await res.json();
          set({
            friendCount: data.friend_count ?? 0,
            groupCount: data.group_count ?? 0,
            systemVersion: data.system_version ?? '',
            lastUpdate: Date.now(),
            loading: false,
          });
        } catch {
          set({ loading: false });
        }
      },
    }),
    { name: 'ai-bot-dashboard' }
  )
);

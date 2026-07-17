import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AuthState } from '../types';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, _get) => ({
      isLoggedIn: false,
      userRole: 'user' as const,
      username: '',
      token: '',

      login: async (username: string, password: string) => {
        try {
          const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
          });
          const data = await res.json();
          if (data.success) {
            set({
              isLoggedIn: true,
              userRole: 'admin',
              username: data.username || username,
              token: data.token,
            });
            sessionStorage.setItem('gracyui_token', data.token);
            return true;
          }
          return false;
        } catch {
          return false;
        }
      },

      logout: () => {
        set({ isLoggedIn: false, userRole: 'user', username: '', token: '' });
        sessionStorage.removeItem('gracyui_token');
      },

      checkAuth: async () => {
        const token = sessionStorage.getItem('gracyui_token');
        if (!token) {
          set({ isLoggedIn: false, userRole: 'user', username: '', token: '' });
          return;
        }
        try {
          const res = await fetch(`/api/auth/verify?token=${token}`);
          const data = await res.json();
          if (data.valid) {
            set({ isLoggedIn: true, userRole: 'admin', username: '主人', token });
          } else {
            sessionStorage.removeItem('gracyui_token');
            set({ isLoggedIn: false, userRole: 'user', username: '', token: '' });
          }
        } catch {
          // 离线时保留登录态
          set({ isLoggedIn: true, userRole: 'admin', username: '主人', token });
        }
      },
    }),
    {
      name: 'ai-bot-auth',
      partialize: (state) => ({
        isLoggedIn: state.isLoggedIn,
        userRole: state.userRole,
        username: state.username,
      }),
    }
  )
);

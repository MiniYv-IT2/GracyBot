import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SessionStoreState, Session } from '../types';

const mockSessions: Session[] = [
  { id: 'session-1', type: 'private', targetId: '123456', lastMessageTime: Date.now() - 60000, messageCount: 25, isActive: true },
  { id: 'session-2', type: 'group', targetId: 'group-001', lastMessageTime: Date.now() - 300000, messageCount: 150, isActive: true },
  { id: 'session-3', type: 'private', targetId: '234567', lastMessageTime: Date.now() - 3600000, messageCount: 80, isActive: false },
];

export const useSessionStore = create<SessionStoreState>()(
  persist(
    (set) => ({
      sessions: mockSessions,
      blacklist: [],
      whitelist: [],

      clearSession: (sessionId) => {
        set((state) => ({
          sessions: state.sessions.filter(s => s.id !== sessionId),
        }));
      },

      addToBlacklist: (targetId) => {
        set((state) => ({
          blacklist: [...state.blacklist, targetId],
        }));
      },

      removeFromBlacklist: (targetId) => {
        set((state) => ({
          blacklist: state.blacklist.filter(id => id !== targetId),
        }));
      },

      addToWhitelist: (targetId) => {
        set((state) => ({
          whitelist: [...state.whitelist, targetId],
        }));
      },

      removeFromWhitelist: (targetId) => {
        set((state) => ({
          whitelist: state.whitelist.filter(id => id !== targetId),
        }));
      },
    }),
    {
      name: 'ai-bot-sessions',
    }
  )
);

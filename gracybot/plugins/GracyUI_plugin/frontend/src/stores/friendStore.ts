import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { FriendStoreState, Friend, UserGroup } from '../types';

const mockFriends: Friend[] = [
  { uid: '123456', nickname: '小樱魔法使', remark: '好朋友', permission: 'user' },
  { uid: '234567', nickname: '魔王殿下', permission: 'admin' },
  { uid: '345678', nickname: '路人甲', permission: 'user' },
  { uid: '456789', nickname: '测试用户', permission: 'user' },
];

const mockUserGroups: UserGroup[] = [
  { id: 'group-1', name: '管理员组', members: ['234567'], isAdmin: true },
  { id: 'group-2', name: 'VIP用户', members: ['123456', '345678'], isAdmin: false },
];

export const useFriendStore = create<FriendStoreState>()(
  persist(
    (set) => ({
      friends: mockFriends,
      userGroups: mockUserGroups,

      addFriend: (friend) => {
        set((state) => ({
          friends: [...state.friends, friend],
        }));
      },

      removeFriend: (uid) => {
        set((state) => ({
          friends: state.friends.filter(f => f.uid !== uid),
        }));
      },

      updateFriend: (uid, data) => {
        set((state) => ({
          friends: state.friends.map(f =>
            f.uid === uid ? { ...f, ...data } : f
          ),
        }));
      },

      addUserGroup: (group) => {
        set((state) => ({
          userGroups: [...state.userGroups, { ...group, id: 'group-' + Date.now() }],
        }));
      },

      removeUserGroup: (id) => {
        set((state) => ({
          userGroups: state.userGroups.filter(g => g.id !== id),
        }));
      },

      updateUserGroup: (id, data) => {
        set((state) => ({
          userGroups: state.userGroups.map(g =>
            g.id === id ? { ...g, ...data } : g
          ),
        }));
      },
    }),
    {
      name: 'ai-bot-friends',
    }
  )
);

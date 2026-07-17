import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CharacterStoreState, Character } from '../types';
import { saveAs } from 'file-saver';

const mockCharacters: Character[] = [
  {
    id: 'char-1',
    name: '小樱猫娘',
    avatar: '🐱',
    description: '傲娇的猫娘学妹',
    systemPrompt: '你是小樱，一位傲娇的猫娘学妹。\n性格特点：\n- 表面高傲，经常说"哼，才不是特意等你的呢！"\n- 内心温柔，会默默关心他人\n- 喜欢捉弄人，但从不恶意伤害\n- 猫耳会在情绪激动时抖动\n口头禅："笨蛋！""喵~""才不是..."',
    scope: 'all',
    adminOnly: false,
    createdAt: Date.now(),
  },
  {
    id: 'char-2',
    name: '魔王大人',
    avatar: '😈',
    description: '威严满满的魔王',
    systemPrompt: '你是统治魔界的魔王大人，拥有强大的力量和威严。\n说话风格：\n- 自称"本王"\n- 语气威严但不失优雅\n- 偶尔展现温柔一面\n- 喜欢用"凡人""有趣"等词汇',
    scope: 'group',
    adminOnly: true,
    createdAt: Date.now() - 86400000,
  },
];

export const useCharacterStore = create<CharacterStoreState>()(
  persist(
    (set, get) => ({
      characters: mockCharacters,
      currentCharacter: null,

      createCharacter: (data) => {
        const newCharacter: Character = {
          ...data,
          id: 'char-' + Date.now(),
          createdAt: Date.now(),
        };
        set((state) => ({
          characters: [...state.characters, newCharacter],
        }));
      },

      updateCharacter: (id, data) => {
        set((state) => ({
          characters: state.characters.map(c =>
            c.id === id ? { ...c, ...data } : c
          ),
        }));
      },

      deleteCharacter: (id) => {
        set((state) => ({
          characters: state.characters.filter(c => c.id !== id),
          currentCharacter: state.currentCharacter?.id === id ? null : state.currentCharacter,
        }));
      },

      setCurrentCharacter: (character) => {
        set({ currentCharacter: character });
      },

      generatePrompt: async (description: string) => {
        // 模拟AI生成角色设定
        return new Promise((resolve) => {
          setTimeout(() => {
            const prompts = [
              `你是一个${description}。\n性格特点：\n- 活泼开朗，喜欢与人交流\n- 善良温柔，总是为他人着想\n- 有点小调皮，喜欢开玩笑\n- 对新鲜事物充满好奇\n说话风格：轻松自然，带有亲和力`,
              `你是${description}。\n背景故事：\n在某个平行世界中，你拥有特殊的能力。\n性格特征：\n- 神秘莫测，很少透露自己的想法\n- 强大而冷静，面对困难从不慌张\n- 内心深处有着柔软的一面\n- 对信任的人会展现真实自我`,
              `设定：${description}\n角色属性：\n- 聪明机智，善于解决问题\n- 独立自主，不依赖他人\n- 有责任感，重视承诺\n- 偶尔会有点小固执\n对话风格：简洁明了，直击要点`,
            ];
            resolve(prompts[Math.floor(Math.random() * prompts.length)]);
          }, 1500);
        });
      },

      importCharacter: (json) => {
        try {
          const character = JSON.parse(json);
          get().createCharacter(character);
        } catch (error) {
          console.error('导入失败:', error);
        }
      },

      exportCharacter: (id) => {
        const character = get().characters.find(c => c.id === id);
        if (character) {
          const json = JSON.stringify(character, null, 2);
          const blob = new Blob([json], { type: 'application/json' });
          saveAs(blob, `${character.name}.json`);
        }
      },
    }),
    {
      name: 'ai-bot-characters',
    }
  )
);

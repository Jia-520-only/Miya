import { create } from 'zustand';
import { EmotionState, Message } from '@shared/types';

interface AppState {
  // 情绪状态
  emotion: EmotionState | null;
  setEmotion: (emotion: EmotionState) => void;

  // 消息
  messages: Message[];
  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;

  // 页面路由
  currentPage: 'chat' | 'emotion' | 'live2d' | 'code' | 'settings';
  setCurrentPage: (page: 'chat' | 'emotion' | 'live2d' | 'code' | 'settings') => void;

  // 悬浮球
  showFloatingBall: boolean;
  setShowFloatingBall: (show: boolean) => void;

  // 快速对话模态框
  showQuickChat: boolean;
  setShowQuickChat: (show: boolean) => void;

  // 设置模态框
  showSettings: boolean;
  setShowSettings: (show: boolean) => void;

  // Live2D 模型路径
  live2dModelPath: string;
  setLive2dModelPath: (path: string) => void;
}

export const useStore = create<AppState>((set) => ({
  // 初始状态
  emotion: null,
  messages: [],
  currentPage: 'chat',
  showFloatingBall: true,
  showQuickChat: false,
  showSettings: false,
  live2dModelPath: 'https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display/test/assets/shizuku/shizuku.model.json',

  // 动作
  setEmotion: (emotion) => set({ emotion }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  setCurrentPage: (currentPage) => set({ currentPage }),
  setShowFloatingBall: (showFloatingBall) => set({ showFloatingBall }),
  setShowQuickChat: (showQuickChat) => set({ showQuickChat }),
  setShowSettings: (showSettings) => set({ showSettings }),
  setLive2dModelPath: (live2dModelPath) => set({ live2dModelPath }),
}));

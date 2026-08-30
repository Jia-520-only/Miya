/**
 * 弥娅 Web 前端状态管理
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, BlogPost, SystemStatus, SecurityEvent } from '../services/api';

// ==================== 认证 Store ====================

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  _hasHydrated: boolean;
  setHasHydrated: (state: boolean) => void;
  login: (user: User, token: string) => void;
  logout: () => void;
}

// 创建 localStorage storage 对象
const localStorageAdapter = {
  getItem: (name: string) => {
    const str = localStorage.getItem(name);
    return str ? JSON.parse(str) : null;
  },
  setItem: (name: string, value: any) => {
    localStorage.setItem(name, JSON.stringify(value));
  },
  removeItem: (name: string) => {
    localStorage.removeItem(name);
  },
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      _hasHydrated: false,
      setHasHydrated: (state) => set({ _hasHydrated: state }),
      login: (user, token) =>
        set({
          user,
          token,
          isAuthenticated: true,
        }),
      logout: () =>
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        }),
    }),
    {
      name: 'miya-auth',
      storage: localStorageAdapter,
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);

// ==================== 博客 Store ====================

interface BlogState {
  posts: BlogPost[];
  currentPost: BlogPost | null;
  loading: boolean;
  total: number;
  page: number;
  totalPages: number;
  setPosts: (posts: BlogPost[], total: number, page: number, totalPages: number) => void;
  setCurrentPost: (post: BlogPost | null) => void;
  setLoading: (loading: boolean) => void;
  addPost: (post: BlogPost) => void;
  updatePost: (slug: string, post: BlogPost) => void;
  deletePost: (slug: string) => void;
}

export const useBlogStore = create<BlogState>((set) => ({
  posts: [],
  currentPost: null,
  loading: false,
  total: 0,
  page: 1,
  totalPages: 1,
  setPosts: (posts, total, page, totalPages) =>
    set({ posts, total, page, totalPages }),
  setCurrentPost: (post) => set({ currentPost: post }),
  setLoading: (loading) => set({ loading }),
  addPost: (post) =>
    set((state) => ({
      posts: [post, ...state.posts],
      total: state.total + 1,
    })),
  updatePost: (slug, updatedPost) =>
    set((state) => ({
      posts: state.posts.map((p) => (p.slug === slug ? updatedPost : p)),
      currentPost: state.currentPost?.slug === slug ? updatedPost : state.currentPost,
    })),
  deletePost: (slug) =>
    set((state) => ({
      posts: state.posts.filter((p) => p.slug !== slug),
      currentPost: state.currentPost?.slug === slug ? null : state.currentPost,
      total: state.total - 1,
    })),
}));

// ==================== 聊天 Store ====================

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ChatState {
  messages: ChatMessage[];
  loading: boolean;
  connected: boolean;
  addMessage: (message: ChatMessage) => void;
  setMessages: (messages: ChatMessage[]) => void;
  setLoading: (loading: boolean) => void;
  setConnected: (connected: boolean) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  loading: false,
  connected: false,
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),
  setMessages: (messages) => set({ messages }),
  setLoading: (loading) => set({ loading }),
  setConnected: (connected) => set({ connected }),
  clearMessages: () => set({ messages: [] }),
}));

// ==================== 系统 Store ====================

interface SystemState {
  status: SystemStatus | null;
  loading: boolean;
  setStatus: (status: SystemStatus) => void;
  setLoading: (loading: boolean) => void;
}

export const useSystemStore = create<SystemState>((set) => ({
  status: null,
  loading: false,
  setStatus: (status) => set({ status }),
  setLoading: (loading) => set({ loading }),
}));

// ==================== 安全 Store ====================

interface SecurityState {
  events: SecurityEvent[];
  blockedIPs: string[];
  totalEvents: number;
  loading: boolean;
  setEvents: (events: SecurityEvent[], total: number) => void;
  setBlockedIPs: (ips: string[]) => void;
  setLoading: (loading: boolean) => void;
  addEvent: (event: SecurityEvent) => void;
  updateEventStatus: (eventId: string, status: string) => void;
}

export const useSecurityStore = create<SecurityState>((set) => ({
  events: [],
  blockedIPs: [],
  totalEvents: 0,
  loading: false,
  setEvents: (events, total) => set({ events, totalEvents: total }),
  setBlockedIPs: (ips) => set({ blockedIPs: ips }),
  setLoading: (loading) => set({ loading }),
  addEvent: (event) =>
    set((state) => ({
      events: [event, ...state.events],
      totalEvents: state.totalEvents + 1,
    })),
  updateEventStatus: (eventId, status) =>
    set((state) => ({
      events: state.events.map((e) =>
        e.id === eventId ? { ...e, status } : e
      ),
    })),
}));

// ==================== UI Store ====================

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark';
  currentPage: string;
  setSidebarOpen: (open: boolean) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  setCurrentPage: (page: string) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      theme: 'light',
      currentPage: 'home',
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setTheme: (theme) => set({ theme }),
      setCurrentPage: (page) => set({ currentPage: page }),
    }),
    {
      name: 'miya-ui',
      storage: localStorageAdapter,
    }
  )
);

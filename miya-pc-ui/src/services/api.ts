/**
 * 弥娅 Web API 服务层
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';

// API 基础配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 token
apiClient.interceptors.request.use(
  (config) => {
    // 尝试从多个可能的存储key中获取token
    let token = localStorage.getItem('miya_token');

    // 如果没有找到,尝试从Zustand persist存储中获取
    if (!token) {
      const authData = localStorage.getItem('miya-auth');
      if (authData) {
        try {
          const parsed = JSON.parse(authData);
          token = parsed.state?.token;
        } catch (e) {
          console.error('解析auth数据失败:', e);
        }
      }
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：统一处理错误
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    console.log('[API Response Success]', {
      status: response.status,
      url: response.config?.url,
      method: response.config?.method
    });
    return response;
  },
  (error) => {
    console.log('[API Response Error]', {
      status: error.response?.status,
      url: error.config?.url,
      method: error.config?.method,
      hasToken: !!error.config?.headers?.Authorization,
      token: error.config?.headers?.Authorization?.substring(0, 30) + '...'
    });

    if (error.response?.status === 401) {
      // Token 过期，清除本地存储
      console.error('[API] 收到401错误,准备清除认证状态');
      console.error('[API] 清除前 localStorage:', {
        'miya-token': localStorage.getItem('miya-token')?.substring(0, 30),
        'miya-auth': localStorage.getItem('miya-auth')?.substring(0, 50),
        'miya-ui': localStorage.getItem('miya-ui')?.substring(0, 30)
      });

      // 获取当前 store 状态
      const authStateStr = localStorage.getItem('miya-auth');
      if (authStateStr) {
        try {
          const authState = JSON.parse(authStateStr);
          console.error('[API] 当前认证状态:', authState);
        } catch (e) {
          console.error('[API] 解析认证状态失败:', e);
        }
      }

      localStorage.removeItem('miya_token');
      localStorage.removeItem('miya_user');
      localStorage.removeItem('miya-auth');

      console.error('[API] 清除后 localStorage:', {
        'miya-token': localStorage.getItem('miya-token'),
        'miya-auth': localStorage.getItem('miya-auth')
      });

      // 使用 window.location.href 强制刷新到登录页
      console.error('[API] 跳转到登录页');
      window.location.href = '/login';
    }

    return Promise.reject(error);
  }
);

// ==================== 博客 API ====================

export interface BlogPost {
  id: string;
  title: string;
  slug: string;
  content: string;
  excerpt: string;
  author: string;
  category: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  published: boolean;
  views: number;
  likes: number;
}

export interface BlogListResponse {
  posts: BlogPost[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export const blogApi = {
  // 获取博客列表
  getPosts: async (params?: {
    page?: number;
    category?: string;
    tag?: string;
  }): Promise<BlogListResponse> => {
    const response = await apiClient.get('/api/blog/posts', { params });
    return response.data;
  },

  // 获取单篇博客
  getPost: async (slug: string): Promise<BlogPost> => {
    const response = await apiClient.get(`/api/blog/posts/${slug}`);
    return response.data;
  },

  // 创建博客
  createPost: async (data: {
    title: string;
    content: string;
    category: string;
    tags: string[];
    published?: boolean;
  }): Promise<BlogPost> => {
    const response = await apiClient.post('/api/blog/posts', data);
    return response.data;
  },

  // 更新博客
  updatePost: async (slug: string, data: {
    title?: string;
    content?: string;
    category?: string;
    tags?: string[];
    published?: boolean;
  }): Promise<BlogPost> => {
    const response = await apiClient.put(`/api/blog/posts/${slug}`, data);
    return response.data;
  },

  // 删除博客
  deletePost: async (slug: string): Promise<void> => {
    await apiClient.delete(`/api/blog/posts/${slug}`);
  },
};

// ==================== 认证 API ====================

export interface User {
  id: string;
  username: string;
  email: string;
  level: number;
  trust_score: number;
  created_at: string;
  last_login: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  user: User;
  token: string;
}

export const authApi = {
  // 注册
  register: async (data: {
    username: string;
    email: string;
    password: string;
  }): Promise<{ success: boolean; message: string; user: User }> => {
    const response = await apiClient.post('/api/auth/register', data);
    return response.data;
  },

  // 登录
  login: async (data: {
    username: string;
    password: string;
  }): Promise<LoginResponse> => {
    const response = await apiClient.post('/api/auth/login', data);
    return response.data;
  },

  // 登出
  logout: async (): Promise<void> => {
    await apiClient.post('/api/auth/logout');
    localStorage.removeItem('miya_token');
    localStorage.removeItem('miya_user');
  },

  // 获取当前用户
  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get('/api/auth/me');
    return response.data;
  },
};

// ==================== 聊天 API ====================

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  timestamp: string;
}

export const chatApi = {
  // 发送消息
  sendMessage: async (data: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post('/api/chat', data);
    return response.data;
  },

  // 获取历史消息
  getHistory: async (limit: number = 50): Promise<ChatMessage[]> => {
    // 后端暂时不支持历史消息，返回空数组
    return [];
  },

  // 获取终端命令历史
  getTerminalHistory: async (limit: number = 20): Promise<{
    success: boolean;
    history: any[];
    statistics: any;
    message?: string;
  }> => {
    const response = await apiClient.get('/api/terminal/history', {
      params: { limit }
    });
    return response.data;
  },

  // 执行终端命令
  executeTerminalCommand: async (command: string, session_id: string = 'web'): Promise<{
    success: boolean;
    command: string;
    response: string;
    error?: string;
    timestamp: string;
  }> => {
    const response = await apiClient.post('/api/terminal/execute', {
      command,
      session_id
    }, {
      params: { command, session_id }
    });
    return response.data;
  },
};

// ==================== 系统 API ====================

export interface SystemStatus {
  identity: {
    name: string;
    version: string;
  };
  personality: {
    state: string;
    dominant: string;
    vectors: Record<string, number>;
  };
  emotion: {
    current: Record<string, number>;
    dominant: string;
    intensity: number;
  };
  memory_stats: {
    tide_count: number;
    dream_count: number;
    total_access: number;
  };
  stats: {
    total_visits?: number;
    total_posts?: number;
    total_users?: number;
  };
  timestamp: string;
}

export const systemApi = {
  // 获取系统状态
  getStatus: async (): Promise<SystemStatus> => {
    const response = await apiClient.get('/api/status');
    return response.data;
  },

  // 获取情绪状态
  getEmotion: async (): Promise<{
    primary: string;
    intensity: number;
    state: string;
    current: Record<string, number>;
  }> => {
    const response = await apiClient.get('/api/emotion');
    return response.data;
  },

  // 健康检查
  health: async (): Promise<{ status: string; timestamp: string; service: string }> => {
    const response = await apiClient.get('/api/health');
    return response.data;
  },

  // 获取平台自动检测能力
  getPlatformCapabilities: async (): Promise<{
    success: boolean;
    capabilities: {
      os: any;
      cpu: any;
      memory: any;
      disk: any;
      network: any;
    };
    timestamp: string;
  }> => {
    const response = await apiClient.get('/api/platform/capabilities');
    return response.data;
  },

  // 获取系统监控数据（实时）
  getMonitor: async (): Promise<{
    success: boolean;
    monitor: {
      cpu: any;
      memory: any;
      disk: any;
      network: any;
      process: any;
    };
    timestamp: string;
  }> => {
    const response = await apiClient.get('/api/system/monitor');
    return response.data;
  },

  // 获取系统日志
  getLogs: async (limit: number = 50, level?: string): Promise<{
    success: boolean;
    log_file: string;
    logs: string[];
    total: number;
    timestamp: string;
  }> => {
    const response = await apiClient.get('/api/system/logs', {
      params: { limit, level }
    });
    return response.data;
  },

  // 获取最近活动
  getRecentActivities: async (limit: number = 10): Promise<{
    success: boolean;
    activities: Array<{
      time: string;
      action: string;
      type: string;
    }>;
    total: number;
    timestamp: string;
  }> => {
    const response = await apiClient.get('/api/system/recent-activities', {
      params: { limit }
    });
    return response.data;
  },
};

// ==================== 安全 API ====================

export interface SecurityEvent {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  source_ip: string;
  user_id: string | null;
  details: Record<string, any>;
  timestamp: string;
  status: string;
}

export const securityApi = {
  // 获取安全事件
  getEvents: async (params?: { severity?: string; limit?: number }): Promise<{
    events: SecurityEvent[];
    total: number;
    timestamp: string;
  }> => {
    // 后端暂时不支持此接口,返回空数组
    return {
      events: [],
      total: 0,
      timestamp: new Date().toISOString()
    };
  },

  // 获取安全状态
  getStatus: async (): Promise<{
    blocked_ips: string[];
    total_events: number;
    critical_events: number;
  }> => {
    // 后端暂时不支持此接口,返回默认状态
    return {
      blocked_ips: [],
      total_events: 0,
      critical_events: 0
    };
  },

  // 安全扫描
  scan: async (data: {
    path: string;
    body?: string;
    params?: Record<string, any>;
  }): Promise<{ detected: boolean; event: SecurityEvent | null }> => {
    const response = await apiClient.post('/api/security/scan', data);
    return response.data;
  },

  // 封禁 IP (需要管理员权限)
  blockIP: async (data: { ip: string; duration?: number }): Promise<{
    success: boolean;
    message: string;
    duration: number;
  }> => {
    const response = await apiClient.post('/api/security/block-ip', data);
    return response.data;
  },
};

// ==================== GitHub API ====================

export interface GitHubConfig {
  repoOwner: string;
  repoName: string;
  token: string;
  branch: string;
}

export const githubApi = {
  // 配置 GitHub
  configure: async (config: GitHubConfig): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post('/api/github/config', config);
    return response.data;
  },

  // 同步 GitHub
  sync: async (): Promise<{ success: boolean; synced_count: number; message: string }> => {
    const response = await apiClient.post('/api/github/sync');
    return response.data;
  },

  // 从 GitHub 拉取
  pull: async (): Promise<{ success: boolean; synced_count: number; message: string }> => {
    const response = await apiClient.post('/api/github/pull');
    return response.data;
  },

  // 推送到 GitHub
  push: async (): Promise<{ success: boolean; pushed_count: number; message: string }> => {
    const response = await apiClient.post('/api/github/push');
    return response.data;
  },

  // 获取 GitHub 状态
  getStatus: async (): Promise<{
    configured: boolean;
    repo: string | null;
    branch: string | null;
    total_files: number;
  }> => {
    const response = await apiClient.get('/api/github/status');
    return response.data;
  },
};

// 导出所有 API
export const api = {
  blog: blogApi,
  auth: authApi,
  chat: chatApi,
  system: systemApi,
  security: securityApi,
  github: githubApi,
};

export default api;

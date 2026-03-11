/**
 * 弥娅 Web 应用主入口
 */

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/webStore';

// 布局组件
import { MainLayout, PublicLayout } from './Web/Layout';

// 页面组件
import { LandingPage, HomePage, LoginPage, RegisterPage } from './Web/Pages';
import TestPage from './Web/Pages/TestPage';
import DashboardPage from './Web/Pages/DashboardPage';
import { BlogList, BlogDetail, BlogEditor, GitHubManager } from './Web/Blog';
import { ChatInterface } from './Web/Chat';
import { SystemStatus } from './Web/Dashboard';
import { SecurityConsole } from './Web/Security';
import { TechPage, TechCategoryPage } from './Web/Tech';
import { CulturePage, CultureCategoryPage } from './Web/Culture';
import { AboutPage } from './Web/About';
import { CommunityPage } from './Web/Community';
import WebConsolePage from './Web/Pages/WebConsolePage';
import SystemMonitorPage from './Web/Pages/SystemMonitorPage';

// 受保护路由组件
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const hasHydrated = useAuthStore((state) => (state as any)._hasHydrated);

  console.log('[ProtectedRoute] 检查认证状态:', {
    hasHydrated,
    isAuthenticated,
    hasUser: !!user,
    hasToken: !!token,
    token: token ? `${token.substring(0, 20)}...` : null,
    localStorageAuth: localStorage.getItem('miya-auth')?.substring(0, 50)
  });

  // 等待状态水合完成
  if (!hasHydrated) {
    console.log('[ProtectedRoute] 等待状态水合...');
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">加载中...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    console.log('[ProtectedRoute] 未认证,重定向到登录页');
    return <Navigate to="/login" replace />;
  }

  console.log('[ProtectedRoute] 认证通过,渲染受保护内容');
  return <>{children}</>;
}

// 公开路由组件
function PublicRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasHydrated = useAuthStore((state) => (state as any)._hasHydrated);

  console.log('[PublicRoute] 检查认证状态:', {
    hasHydrated,
    isAuthenticated
  });

  // 等待状态水合完成
  if (!hasHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-400">加载中...</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    console.log('[PublicRoute] 已登录,重定向到仪表板');
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <Router>
      <Routes>
        {/* 公开路由 */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/test" element={<TestPage />} />
        <Route path="/tech" element={<TechPage />} />
        <Route path="/tech/:categoryId" element={<TechCategoryPage />} />
        <Route path="/culture" element={<CulturePage />} />
        <Route path="/culture/:categoryId" element={<CultureCategoryPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/community" element={<CommunityPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* 受保护路由 - 首页 (已登录用户的首页) */}
        <Route
          path="/home"
          element={
            <ProtectedRoute>
              <MainLayout>
                <HomePage />
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* 博客路由 - 重要: 更具体的路由要放在前面 */}
        <Route
          path="/blog/new"
          element={
            <ProtectedRoute>
              <MainLayout>
                <BlogEditor />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/blog/:slug/edit"
          element={
            <ProtectedRoute>
              <MainLayout>
                <BlogEditor />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/blog/github"
          element={
            <ProtectedRoute>
              <MainLayout>
                <GitHubManager />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/blog/:slug"
          element={
            <ProtectedRoute>
              <MainLayout>
                <BlogDetail />
              </MainLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/blog"
          element={
            <ProtectedRoute>
              <MainLayout>
                <BlogList />
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* 聊天路由 */}
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <MainLayout>
                <ChatInterface />
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* 仪表板路由 */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <MainLayout>
                <SystemStatus />
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* 安全控制台路由 */}
        <Route
          path="/security"
          element={
            <ProtectedRoute>
              <MainLayout>
                <SecurityConsole />
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* Web控制台路由 - Web端掌控者主控中心 */}
        <Route
          path="/console"
          element={
            <ProtectedRoute>
              <MainLayout>
                <WebConsolePage />
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* 系统监控路由 */}
        <Route
          path="/monitor"
          element={
            <ProtectedRoute>
              <MainLayout>
                <SystemMonitorPage />
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* 404 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

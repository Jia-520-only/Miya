/**
 * 头部导航栏组件 - 柔和青蓝色调
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore, useUIStore } from '../../store/webStore';

export default function Header() {
  const { user, isAuthenticated, logout } = useAuthStore();
  const { theme, setTheme, sidebarOpen, setSidebarOpen } = useUIStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // 处理退出登录
  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('退出登录失败:', error);
    }
  };

  // 应用主题
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // 导航菜单
  const navItems = [
    { path: '/', label: '首页' },
    { path: '/blog', label: '博客' },
    { path: '/chat', label: '聊天' },
    { path: '/console', label: '控制台' },
    { path: '/monitor', label: '监控' },
    { path: '/dashboard', label: '仪表板' },
    { path: '/security', label: '安全' },
  ];

  return (
    <header className="glass border-b border-miya-200/30 dark:border-miya-700/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo 和侧边栏切换 */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2.5 rounded-xl hover:bg-white/50 dark:hover:bg-miya-800/50 text-miya-600 dark:text-miya-400 transition-all hover:scale-110"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-miya-400 to-sky-400 flex items-center justify-center text-white text-xl font-bold shadow-soft group-hover:scale-110 transition-transform">
                M
              </div>
              <span className="text-2xl font-bold text-gradient">弥娅</span>
            </Link>
          </div>

          {/* 桌面端导航 */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all hover:scale-105 ${
                  location.pathname === item.path
                    ? 'bg-gradient-to-r from-miya-400 to-sky-400 text-white shadow-soft'
                    : 'text-miya-700 dark:text-miya-300 hover:bg-white/40 dark:hover:bg-miya-800/40'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* 右侧操作区 */}
          <div className="flex items-center gap-3">
            {/* 主题切换 */}
            <button
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              className="p-2.5 rounded-xl hover:bg-white/50 dark:hover:bg-miya-800/50 text-miya-600 dark:text-miya-400 transition-all hover:scale-110"
              title={theme === 'light' ? '切换到深色模式' : '切换到浅色模式'}
            >
              {theme === 'light' ? (
                <span className="text-xl">🌙</span>
              ) : (
                <span className="text-xl">🌸</span>
              )}
            </button>

            {/* 用户菜单 */}
            {isAuthenticated ? (
              <div className="relative">
                <button
                  onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                  className="flex items-center gap-2.5 p-2 rounded-xl hover:bg-white/50 dark:hover:bg-miya-800/50 transition-all hover:scale-110"
                >
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-miya-400 to-sky-400 flex items-center justify-center text-white font-bold shadow-soft">
                    {user?.username[0].toUpperCase()}
                  </div>
                  <span className="hidden md:block text-sm font-semibold text-miya-700 dark:text-miya-300">
                    {user?.username}
                  </span>
                </button>

                {isMobileMenuOpen && (
                  <div className="absolute right-0 mt-2 w-52 glass rounded-2xl shadow-card py-2 animate-slide-up">
                    <Link
                      to="/profile"
                      className="block px-5 py-3 text-sm font-medium text-miya-700 dark:text-miya-300 hover:bg-miya-100/50 dark:hover:bg-miya-800/50 transition-colors"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      👤 个人资料
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="w-full text-left px-5 py-3 text-sm font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                      🚪 退出登录
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link
                to="/login"
                className="btn-primary px-6 py-2.5 rounded-2xl text-sm font-semibold"
              >
                登录
              </Link>
            )}

            {/* 移动端菜单按钮 */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="md:hidden p-2.5 rounded-xl hover:bg-white/50 dark:hover:bg-miya-800/50 text-miya-600 dark:text-miya-400 transition-all hover:scale-110"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* 移动端导航菜单 */}
      {isMobileMenuOpen && (
        <div className="md:hidden glass border-t border-miya-200/30 dark:border-miya-700/30 py-4 animate-slide-up">
          <nav className="flex flex-col space-y-2 px-4">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`px-5 py-3 rounded-xl text-sm font-medium transition-all ${
                  location.pathname === item.path
                    ? 'bg-gradient-to-r from-miya-400 to-sky-400 text-white shadow-soft'
                    : 'text-miya-700 dark:text-miya-300 hover:bg-white/40 dark:hover:bg-miya-800/40'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}

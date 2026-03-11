/**
 * 侧边栏组件
 */

import { useLocation, Link } from 'react-router-dom';
import { useUIStore } from '../../store/webStore';

export default function Sidebar() {
  const { sidebarOpen } = useUIStore();
  const location = useLocation();

  if (!sidebarOpen) return null;

  const menuItems = [
    {
      category: '主菜单',
      items: [
        { path: '/', icon: '🏠', label: '首页' },
        { path: '/blog', icon: '📝', label: '博客' },
        { path: '/chat', icon: '💬', label: '聊天' },
      ],
    },
    {
      category: 'Web端掌控者',
      items: [
        { path: '/console', icon: '🎛️', label: 'Web控制台' },
        { path: '/monitor', icon: '🖥️', label: '系统监控' },
      ],
    },
    {
      category: '管理',
      items: [
        { path: '/dashboard', icon: '📊', label: '仪表板' },
        { path: '/security', icon: '🔒', label: '安全控制台' },
        { path: '/blog/github', icon: '🐙', label: 'GitHub 集成' },
      ],
    },
  ];

  return (
    <aside className="fixed left-0 top-16 bottom-0 w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto z-40">
      <div className="py-6 space-y-6">
        {menuItems.map((group) => (
          <div key={group.category}>
            <h3 className="px-6 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
              {group.category}
            </h3>
            <nav className="space-y-1">
              {group.items.map((item) => {
                const isActive = location.pathname === item.path || 
                  (item.path !== '/' && location.pathname.startsWith(item.path));
                
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center gap-3 px-6 py-3 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border-r-2 border-blue-600 dark:border-blue-400'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                    }`}
                  >
                    <span className="text-lg">{item.icon}</span>
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        ))}
      </div>

      {/* 侧边栏底部信息 */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 dark:border-gray-700">
        <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg p-4 text-white">
          <p className="text-sm font-medium">弥娅 AI</p>
          <p className="text-xs text-blue-100 mt-1">智能管家系统</p>
        </div>
      </div>
    </aside>
  );
}

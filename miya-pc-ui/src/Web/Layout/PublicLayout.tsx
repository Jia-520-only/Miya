/**
 * 公开页面布局
 * 用于未登录状态的页面
 */

import PublicHeader from './PublicHeader';

interface PublicLayoutProps {
  children: React.ReactNode;
}

export function PublicLayout({ children }: PublicLayoutProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-gray-900 dark:via-slate-900 dark:to-gray-900">
      <PublicHeader />
      <main>{children}</main>
      <footer className="bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-600 dark:text-gray-400">
            <p className="mb-2">
              &copy; 2026 弥娅 Miya. All rights reserved.
            </p>
            <p className="text-sm">
              <span className="mx-2">技术分享</span>
              <span>•</span>
              <span className="mx-2">生活记录</span>
              <span>•</span>
              <span className="mx-2">社区互动</span>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

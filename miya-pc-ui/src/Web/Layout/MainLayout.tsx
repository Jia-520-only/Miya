/**
 * 主布局组件 - 柔和青蓝色调
 */

import Header from './Header';
import Sidebar from './Sidebar';
import { useUIStore } from '../../store/webStore';

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  const { sidebarOpen } = useUIStore();

  return (
    <div className="min-h-screen bg-gradient-to-br from-miya-50 via-sky-100 to-miya-100 dark:from-miya-900 dark:via-miya-800 dark:to-miya-900">
      {/* 柔和的光晕背景装饰 */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-96 h-96 bg-gradient-to-br from-miya-200/30 to-sky-200/30 rounded-full blur-3xl animate-float"></div>
        <div className="absolute bottom-20 right-20 w-80 h-80 bg-gradient-to-br from-sky-200/20 to-miya-200/20 rounded-full blur-2xl animate-float" style={{ animationDelay: '2s' }}></div>
      </div>

      <Header />
      <div className="pt-16 relative">
        {sidebarOpen ? (
          <div className="flex">
            <Sidebar />
            <main className="flex-1 p-6 ml-64 min-h-[calc(100vh-4rem)]">
              <div className="card rounded-2xl p-8">
                {children}
              </div>
            </main>
          </div>
        ) : (
          <main className="p-6 max-w-7xl mx-auto min-h-[calc(100vh-4rem)]">
            <div className="card rounded-2xl p-8 animate-slide-up">
              {children}
            </div>
          </main>
        )}
      </div>
    </div>
  );
}

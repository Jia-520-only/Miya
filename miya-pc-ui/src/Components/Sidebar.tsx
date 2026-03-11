import React from 'react';
import { useStore } from '@store/useStore';

export const Sidebar: React.FC = () => {
  const { currentPage, setCurrentPage, setShowSettings } = useStore();

  const menuItems = [
    { id: 'chat' as const, label: '💬 对话', icon: '💬' },
    { id: 'emotion' as const, label: '😊 情绪', icon: '😊' },
    { id: 'live2d' as const, label: '🎭 Live2D', icon: '🎭' },
    { id: 'code' as const, label: '💻 代码', icon: '💻' },
  ];

  return (
    <div className="w-64 bg-gradient-to-b from-indigo-900 to-purple-900 text-white flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-indigo-700">
        <h1 className="text-2xl font-bold">🌸 弥娅</h1>
        <p className="text-sm text-indigo-300 mt-1">数字生命伴侣</p>
      </div>

      {/* 导航菜单 */}
      <nav className="flex-1 p-4 space-y-2">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setCurrentPage(item.id)}
            className={`w-full px-4 py-3 rounded-lg text-left transition-colors ${
              currentPage === item.id
                ? 'bg-indigo-700 text-white'
                : 'text-indigo-200 hover:bg-indigo-800'
            }`}
          >
            <span className="mr-2">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* 设置按钮 */}
      <div className="p-4 border-t border-indigo-700">
        <button
          onClick={() => setShowSettings(true)}
          className="w-full px-4 py-3 rounded-lg text-left text-indigo-200 hover:bg-indigo-800 transition-colors"
        >
          ⚙️ 设置
        </button>
      </div>
    </div>
  );
};

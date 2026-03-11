import React, { useState } from 'react';
import { useStore } from '@store/useStore';
import { emotionAPI } from '@shared/api';

export const SettingsPage: React.FC = () => {
  const { live2dModelPath, setLive2dModelPath, setShowSettings } = useStore();
  const [modelPath, setModelPath] = useState(live2dModelPath);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      setLive2dModelPath(modelPath);
      // 这里可以保存到本地存储或后端
      await new Promise(resolve => setTimeout(resolve, 500));
      alert('设置已保存');
      setShowSettings(false);
    } catch (error) {
      console.error('保存设置失败:', error);
      alert('保存设置失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="h-screen bg-gray-50 overflow-auto">
      <div className="max-w-2xl mx-auto py-8 px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">设置</h1>

        <div className="bg-white rounded-lg shadow p-6 space-y-6">
          {/* Live2D 模型设置 */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Live2D 模型</h2>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                模型路径
              </label>
              <input
                type="text"
                value={modelPath}
                onChange={(e) => setModelPath(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                placeholder="输入 Live2D 模型路径"
              />
              <p className="text-xs text-gray-500">
                支持本地路径或远程 URL
              </p>
            </div>
          </div>

          {/* 外观设置 */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">外观</h2>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                主题
              </label>
              <select className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                <option value="dark">深色</option>
                <option value="light">浅色</option>
                <option value="auto">自动</option>
              </select>
            </div>
          </div>

          {/* 悬浮球设置 */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">悬浮球</h2>
            <div className="space-y-2">
              <label className="flex items-center">
                <input type="checkbox" className="rounded" defaultChecked />
                <span className="ml-2 text-sm text-gray-700">启用悬浮球</span>
              </label>
              <label className="flex items-center">
                <input type="checkbox" className="rounded" />
                <span className="ml-2 text-sm text-gray-700">显示情绪指示器</span>
              </label>
            </div>
          </div>

          {/* API 设置 */}
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">API</h2>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                后端地址
              </label>
              <input
                type="text"
                defaultValue="http://localhost:8000"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                placeholder="输入后端 API 地址"
              />
            </div>
          </div>
        </div>

        {/* 保存按钮 */}
        <div className="mt-6 flex justify-end space-x-3">
          <button
            onClick={() => setShowSettings(false)}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-indigo-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
};

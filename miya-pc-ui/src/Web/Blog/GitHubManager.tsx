/**
 * GitHub 仓库管理组件
 */

import { useState, useEffect } from 'react';
import { api } from '../../services/api';
import type { GitHubConfig } from '../../services/api';

export default function GitHubManager() {
  const [config, setConfig] = useState<GitHubConfig>({
    repoOwner: '',
    repoName: '',
    token: '',
    branch: 'main',
  });
  const [isConfigured, setIsConfigured] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    // 从 localStorage 读取配置
    const savedConfig = localStorage.getItem('github_config');
    if (savedConfig) {
      setConfig(JSON.parse(savedConfig));
      setIsConfigured(true);
      fetchStatus();
    }

    const lastSyncTime = localStorage.getItem('github_last_sync');
    if (lastSyncTime) {
      setLastSync(new Date(lastSyncTime));
    }
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await api.github.getStatus();
      setStatus(response);
    } catch (error) {
      console.error('获取 GitHub 状态失败:', error);
    }
  };

  const handleSaveConfig = async () => {
    if (!config.repoOwner || !config.repoName || !config.token) {
      alert('请填写完整的配置信息');
      return;
    }

    try {
      // 转换为后端期望的格式 (使用下划线命名)
      const backendConfig = {
        repo_owner: config.repoOwner,
        repo_name: config.repoName,
        token: config.token,
        branch: config.branch
      };

      const response = await api.github.configure(backendConfig);
      if (response.success) {
        localStorage.setItem('github_config', JSON.stringify(config));
        setIsConfigured(true);
        alert('GitHub 配置已保存');
        fetchStatus();
      }
    } catch (error: any) {
      console.error('配置失败:', error);
      alert(error.response?.data?.detail || '配置失败');
    }
  };

  const handleClearConfig = () => {
    if (window.confirm('确定要清除 GitHub 配置吗?')) {
      localStorage.removeItem('github_config');
      setConfig({
        repoOwner: '',
        repoName: '',
        token: '',
        branch: 'main',
      });
      setIsConfigured(false);
      setStatus(null);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const response = await api.github.sync();
      if (response.success) {
        alert(`同步成功: ${response.synced_count} 个文件`);
        setLastSync(new Date());
        localStorage.setItem('github_last_sync', new Date().toISOString());
      }
    } catch (error: any) {
      console.error('同步失败:', error);
      alert(error.response?.data?.detail || '同步失败');
    } finally {
      setSyncing(false);
    }
  };

  const handlePull = async () => {
    setSyncing(true);
    try {
      const response = await api.github.pull();
      if (response.success) {
        alert(`从 GitHub 拉取成功: ${response.synced_count} 篇文章`);
        setLastSync(new Date());
        localStorage.setItem('github_last_sync', new Date().toISOString());
      }
    } catch (error: any) {
      console.error('拉取失败:', error);
      alert(error.response?.data?.detail || '拉取失败');
    } finally {
      setSyncing(false);
    }
  };

  const handlePush = async () => {
    setSyncing(true);
    try {
      const response = await api.github.push();
      if (response.success) {
        alert(`推送到 GitHub 成功: ${response.pushed_count} 篇文章`);
        setLastSync(new Date());
        localStorage.setItem('github_last_sync', new Date().toISOString());
      }
    } catch (error: any) {
      console.error('推送失败:', error);
      alert(error.response?.data?.detail || '推送失败');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="text-4xl">🐙</div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              GitHub 集成
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              将博客文章存储到 GitHub 仓库
            </p>
          </div>
        </div>

        {/* 仓库状态 */}
        {status && status.configured && (
          <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/30 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-green-600 dark:text-green-400">✓</span>
              <span className="font-medium text-green-900 dark:text-green-200">
                仓库已连接
              </span>
            </div>
            <div className="text-sm text-green-800 dark:text-green-300">
              <p>仓库: <code className="bg-green-100 dark:bg-green-800 px-1 rounded">{status.repo}</code></p>
              <p>分支: <code className="bg-green-100 dark:bg-green-800 px-1 rounded">{status.branch}</code></p>
              <p>文章数: {status.total_files}</p>
            </div>
          </div>
        )}

        {/* 配置表单 */}
        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              仓库所有者
            </label>
            <input
              type="text"
              value={config.repoOwner}
              onChange={(e) => setConfig({ ...config, repoOwner: e.target.value })}
              placeholder="例如: octocat"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              仓库名称
            </label>
            <input
              type="text"
              value={config.repoName}
              onChange={(e) => setConfig({ ...config, repoName: e.target.value })}
              placeholder="例如: my-blog"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Personal Access Token
            </label>
            <input
              type="password"
              value={config.token}
              onChange={(e) => setConfig({ ...config, token: e.target.value })}
              placeholder="ghp_xxxxxxxxxxxx"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              需要具有 <code className="bg-gray-100 dark:bg-gray-700 px-1 rounded">repo</code> 权限
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              分支名称
            </label>
            <input
              type="text"
              value={config.branch}
              onChange={(e) => setConfig({ ...config, branch: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            />
          </div>
        </div>

        {/* 配置按钮 */}
        <div className="flex gap-3 mb-6">
          <button
            onClick={handleSaveConfig}
            disabled={syncing}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            保存配置
          </button>
          {isConfigured && (
            <button
              onClick={handleClearConfig}
              disabled={syncing}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              清除配置
            </button>
          )}
        </div>

        {/* 同步操作 */}
        {isConfigured && (
          <div className="border-t border-gray-200 dark:border-gray-700 pt-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              同步操作
            </h2>

            {lastSync && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                上次同步: {lastSync.toLocaleString('zh-CN')}
              </p>
            )}

            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={handlePull}
                disabled={syncing}
                className="px-4 py-3 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="text-2xl mb-1">⬇️</div>
                <div className="text-sm font-medium">拉取</div>
              </button>

              <button
                onClick={handlePush}
                disabled={syncing}
                className="px-4 py-3 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="text-2xl mb-1">⬆️</div>
                <div className="text-sm font-medium">推送</div>
              </button>

              <button
                onClick={handleSync}
                disabled={syncing}
                className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="text-2xl mb-1">🔄</div>
                <div className="text-sm font-medium">同步</div>
              </button>
            </div>

            {syncing && (
              <div className="mt-4 flex items-center justify-center gap-2 text-blue-600 dark:text-blue-400">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current"></div>
                <span>同步中...</span>
              </div>
            )}
          </div>
        )}

        {/* 帮助信息 */}
        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
          <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-2">
            💡 使用说明
          </h3>
          <ul className="text-sm text-blue-800 dark:text-blue-300 space-y-1">
            <li>1. 在 GitHub 创建一个新仓库用于存储博客文章</li>
            <li>2. 生成 Personal Access Token (需要 repo 权限)</li>
            <li>3. 填写仓库信息并保存配置</li>
            <li>4. 点击同步按钮将文章推送到 GitHub</li>
            <li>5. 文章会存储在 <code className="bg-blue-100 dark:bg-blue-800 px-1 rounded">posts/</code> 目录下</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

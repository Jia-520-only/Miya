/**
 * 系统状态组件
 */

import { useEffect } from 'react';
import { useSystemStore } from '../../store/webStore';
import { systemApi } from '../../services/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

export default function SystemStatus() {
  const { status, loading, setStatus, setLoading } = useSystemStore();

  // 获取系统状态
  const fetchStatus = async () => {
    setLoading(true);
    try {
      const data = await systemApi.getStatus();
      setStatus(data);
    } catch (error) {
      console.error('获取系统状态失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    // 每 30 秒刷新一次
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // 情绪颜色映射
  const getEmotionColor = (emotion: string | undefined) => {
    if (!emotion) return '#6b7280';
    const colors: Record<string, string> = {
      happy: '#10b981',
      sad: '#6366f1',
      angry: '#ef4444',
      calm: '#3b82f6',
      excited: '#f59e0b',
      confused: '#8b5cf6',
    };
    return colors[emotion.toLowerCase()] || '#6b7280';
  };

  if (loading || !status) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 身份信息 */}
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg p-6 text-white">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center text-2xl font-bold">
            M
          </div>
          <div>
            <h1 className="text-3xl font-bold">{status.identity.name}</h1>
            <p className="text-blue-100">版本: {status.identity.version}</p>
          </div>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">总访问量</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {(status.stats?.total_visits || 0).toLocaleString()}
              </p>
            </div>
            <div className="text-4xl">👁</div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">博客文章</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {status.stats?.total_posts || 0}
              </p>
            </div>
            <div className="text-4xl">📝</div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">注册用户</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {status.stats?.total_users || 0}
              </p>
            </div>
            <div className="text-4xl">👥</div>
          </div>
        </div>
      </div>

      {/* 情绪状态 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          情绪状态
        </h2>
        <div className="flex items-center gap-6">
          <div
            className="w-24 h-24 rounded-full flex items-center justify-center text-white text-2xl font-bold"
            style={{ backgroundColor: getEmotionColor(status.emotion?.dominant) }}
          >
            {status.emotion?.dominant || '未知'}
          </div>
          <div className="flex-1 space-y-2">
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">主要情绪</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white">
                {status.emotion?.dominant || '未知'}
              </p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">情绪强度</p>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                <div
                  className="h-3 rounded-full transition-all duration-300"
                  style={{
                    width: `${(status.emotion?.intensity || 0) * 100}%`,
                    backgroundColor: getEmotionColor(status.emotion?.dominant),
                  }}
                />
              </div>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">当前情绪值</p>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {status.emotion?.current && Object.entries(status.emotion.current).map(([emotion, value]) => (
                  <div key={emotion} className="bg-gray-50 dark:bg-gray-700 rounded p-2 text-sm">
                    <span className="text-gray-600 dark:text-gray-400">{emotion}:</span>
                    <span className="ml-2 font-bold text-gray-900 dark:text-white">
                      {Math.round((value as number) * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 记忆统计 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          记忆统计
        </h2>
        <div className="space-y-3">
          <div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">潮汐记忆</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {status.memory_stats?.tide_count || 0}
            </p>
          </div>
          <div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">梦境记忆</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {status.memory_stats?.dream_count || 0}
            </p>
          </div>
          <div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">总访问次数</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {status.memory_stats?.total_access || 0}
            </p>
          </div>
        </div>
      </div>

      {/* 刷新时间 */}
      <div className="text-center text-sm text-gray-500 dark:text-gray-400">
        最后更新: {new Date(status.timestamp).toLocaleString('zh-CN')}
      </div>
    </div>
  );
}

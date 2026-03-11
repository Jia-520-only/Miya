/**
 * 安全控制台组件
 */

import { useEffect, useState } from 'react';
import { useSecurityStore } from '../../store/webStore';
import { securityApi } from '../../services/api';

export default function SecurityConsole() {
  const { events, blockedIPs, totalEvents, loading, setEvents, setBlockedIPs, setLoading, updateEventStatus } = useSecurityStore();
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');

  // 获取安全事件
  const fetchEvents = async (severity?: string) => {
    setLoading(true);
    try {
      const response = await securityApi.getEvents({ severity: severity === 'all' ? undefined : severity });
      setEvents(response.events, response.total);
    } catch (error) {
      console.error('获取安全事件失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 获取安全状态
  const fetchSecurityStatus = async () => {
    try {
      const status = await securityApi.getStatus();
      setBlockedIPs(status.blocked_ips || []);
    } catch (error) {
      console.error('获取安全状态失败:', error);
    }
  };

  useEffect(() => {
    fetchEvents();
    fetchSecurityStatus();
    // 每 10 秒刷新一次
    const interval = setInterval(() => {
      fetchEvents(selectedSeverity);
      fetchSecurityStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, [selectedSeverity]);

  // 封禁 IP
  const handleBlockIP = async (ip: string) => {
    try {
      await securityApi.blockIP({ ip, duration: 3600 });
      alert(`已封禁 IP: ${ip}`);
      fetchSecurityStatus();
    } catch (error) {
      console.error('封禁 IP 失败:', error);
      alert('封禁失败');
    }
  };

  // 严重程度颜色映射
  const getSeverityColor = (severity: string) => {
    const colors: Record<string, string> = {
      low: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
      medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      high: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      critical: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    };
    return colors[severity] || colors.low;
  };

  // 事件类型中文映射
  const getEventTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      sql_injection: 'SQL 注入',
      xss: 'XSS 攻击',
      ddos: 'DDoS 攻击',
      brute_force: '暴力破解',
      path_traversal: '路径遍历',
      ip_blocked: 'IP 已封禁',
      rate_limit: '频率限制',
    };
    return labels[type] || type;
  };

  // 格式化时间
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            安全控制台
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            监控和管理网站安全
          </p>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">总事件数</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {totalEvents}
              </p>
            </div>
            <div className="text-4xl">⚠️</div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">已封禁 IP</p>
              <p className="text-3xl font-bold text-red-600">
                {blockedIPs.length}
              </p>
            </div>
            <div className="text-4xl">🚫</div>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 dark:text-gray-400 text-sm">高风险事件</p>
              <p className="text-3xl font-bold text-orange-600">
                {events.filter(e => e.severity === 'high' || e.severity === 'critical').length}
              </p>
            </div>
            <div className="text-4xl">🔥</div>
          </div>
        </div>
      </div>

      {/* 已封禁 IP 列表 */}
      {blockedIPs.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-md">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
            已封禁 IP
          </h2>
          <div className="flex flex-wrap gap-2">
            {blockedIPs.map((ip) => (
              <div
                key={ip}
                className="inline-flex items-center gap-2 px-3 py-2 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 rounded-lg"
              >
                <span className="font-mono">{ip}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 安全事件列表 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              安全事件
            </h2>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            >
              <option value="all">全部</option>
              <option value="critical">严重</option>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            暂无安全事件
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {events.map((event) => (
              <div key={event.id} className="p-6 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span
                        className={`px-3 py-1 rounded-full text-sm font-medium ${getSeverityColor(event.severity)}`}
                      >
                        {getEventTypeLabel(event.type)}
                      </span>
                      <span className="text-sm text-gray-500 dark:text-gray-400">
                        {formatTime(event.timestamp)}
                      </span>
                    </div>
                    <div className="space-y-1 text-sm">
                      <p className="text-gray-700 dark:text-gray-300">
                        <span className="font-medium">来源 IP:</span>{' '}
                        <span className="font-mono">{event.source_ip}</span>
                      </p>
                      <p className="text-gray-700 dark:text-gray-300">
                        <span className="font-medium">状态:</span> {event.status}
                      </p>
                      {event.user_id && (
                        <p className="text-gray-700 dark:text-gray-300">
                          <span className="font-medium">用户 ID:</span> {event.user_id}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {event.status === 'detected' && event.source_ip && !event.type.includes('blocked') && (
                      <button
                        onClick={() => handleBlockIP(event.source_ip)}
                        className="px-3 py-1 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition-colors"
                      >
                        封禁 IP
                      </button>
                    )}
                    {event.status === 'detected' && (
                      <button
                        onClick={() => updateEventStatus(event.id, 'resolved')}
                        className="px-3 py-1 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 transition-colors"
                      >
                        标记已解决
                      </button>
                    )}
                  </div>
                </div>
                {Object.keys(event.details).length > 0 && (
                  <details className="mt-3">
                    <summary className="text-sm text-blue-600 dark:text-blue-400 cursor-pointer">
                      查看详情
                    </summary>
                    <pre className="mt-2 p-3 bg-gray-100 dark:bg-gray-900 rounded text-xs overflow-x-auto">
                      {JSON.stringify(event.details, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

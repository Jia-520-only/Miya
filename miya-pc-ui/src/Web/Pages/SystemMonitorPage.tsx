/**
 * 系统监控页面 - 弥娅Web端掌控者的实时监控中心
 */

import { useState, useEffect } from 'react';
import { systemApi } from '../../services/api';

interface MonitorData {
  cpu: {
    cores: number;
    threads: number;
    usage_percent: number;
    per_core: number[];
  };
  memory: {
    total_gb: number;
    available_gb: number;
    used_gb: number;
    usage_percent: number;
  };
  disk: {
    total_gb: number;
    free_gb: number;
    usage_percent: number;
  };
  network: {
    connections: number;
    interfaces: string[];
    bytes_sent: number;
    bytes_recv: number;
  };
  process: {
    total: number;
    running: number;
  };
}

interface LogEntry {
  time: string;
  level: string;
  message: string;
}

export default function SystemMonitorPage() {
  const [monitorData, setMonitorData] = useState<MonitorData | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载监控数据
  const loadMonitorData = async () => {
    try {
      setRefreshing(true);
      const result = await systemApi.getMonitor();
      if (result.success && result.monitor) {
        setMonitorData(result.monitor);
        setError(null);
      } else {
        setError('获取监控数据失败');
      }
    } catch (err: any) {
      setError(err.message || '网络错误');
    } finally {
      setRefreshing(false);
    }
  };

  // 加载日志
  const loadLogs = async () => {
    try {
      const result = await systemApi.getLogs(20);
      if (result.success && result.logs) {
        const parsedLogs = result.logs
          .filter((log: string) => log && log.trim())
          .map((log: string) => {
            const parts = log.split('] ');
            const timestamp = parts[0]?.replace('[', '') || '';
            const levelMatch = log.match(/\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]/);
            const level = levelMatch ? levelMatch[1] : 'INFO';
            const message = parts.slice(1).join('] ') || log;
            return {
              time: timestamp,
              level,
              message
            };
          });
        setLogs(parsedLogs.slice(0, 20));
      }
    } catch (err: any) {
      console.error('加载日志失败:', err);
    }
  };

  useEffect(() => {
    loadMonitorData();
    loadLogs();

    // 每5秒刷新监控数据
    const interval = setInterval(() => {
      loadMonitorData();
    }, 5000);

    // 每30秒刷新日志
    const logInterval = setInterval(() => {
      loadLogs();
    }, 30000);

    return () => {
      clearInterval(interval);
      clearInterval(logInterval);
    };
  }, []);

  const getCpuColor = (usage: number) => {
    if (usage < 30) return 'bg-green-400';
    if (usage < 60) return 'bg-yellow-400';
    if (usage < 80) return 'bg-orange-400';
    return 'bg-red-400';
  };

  const getMemoryColor = (usage: number) => {
    if (usage < 50) return 'bg-green-400';
    if (usage < 75) return 'bg-yellow-400';
    if (usage < 90) return 'bg-orange-400';
    return 'bg-red-400';
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'DEBUG': return 'text-gray-400';
      case 'INFO': return 'text-blue-400';
      case 'WARNING': return 'text-yellow-400';
      case 'ERROR': return 'text-orange-400';
      case 'CRITICAL': return 'text-red-400';
      default: return 'text-gray-300';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* 头部 */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">
                🖥️ 系统监控中心
              </h1>
              <p className="text-purple-300">
                弥娅Web端掌控者 · 实时监控您的系统
              </p>
            </div>
            <button
              onClick={() => { loadMonitorData(); loadLogs(); }}
              disabled={refreshing}
              className={`px-4 py-2 rounded-lg font-semibold text-white transition-all ${
                refreshing
                  ? 'bg-purple-400/50 cursor-wait'
                  : 'bg-purple-500 hover:bg-purple-600'
              }`}
            >
              {refreshing ? '刷新中...' : '🔄 刷新'}
            </button>
          </div>

          {error && (
            <div className="mt-4 bg-red-500/20 border border-red-500/50 rounded-lg p-4">
              <p className="text-red-200">⚠️ {error}</p>
            </div>
          )}
        </div>

        {loading && !monitorData ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-purple-500"></div>
            <p className="ml-4 text-purple-300">正在连接监控系统...</p>
          </div>
        ) : monitorData ? (
          <>
            {/* CPU监控 */}
            <div className="mb-6 bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
              <h2 className="text-xl font-bold text-white mb-4">💻 CPU 使用率</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div>
                  <div className="mb-4">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-purple-300">总体使用率</span>
                      <span className={`text-2xl font-bold ${monitorData.cpu.usage_percent < 50 ? 'text-green-400' : monitorData.cpu.usage_percent < 80 ? 'text-yellow-400' : 'text-red-400'}`}>
                        {monitorData.cpu.usage_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-4 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${getCpuColor(monitorData.cpu.usage_percent)}`}
                        style={{ width: `${monitorData.cpu.usage_percent}%` }}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-purple-300">物理核心</p>
                      <p className="text-white font-semibold">{monitorData.cpu.cores} 核</p>
                    </div>
                    <div>
                      <p className="text-purple-300">逻辑线程</p>
                      <p className="text-white font-semibold">{monitorData.cpu.threads} 线程</p>
                    </div>
                  </div>
                </div>
                <div>
                  <p className="text-purple-300 text-sm mb-2">每核心使用率</p>
                  <div className="grid grid-cols-4 gap-1">
                    {monitorData.cpu.per_core.map((usage, index) => (
                      <div key={index} className="flex flex-col items-center">
                        <div
                          className={`h-16 w-full rounded ${getCpuColor(usage)}`}
                          style={{ opacity: 0.6 + (usage / 200) }}
                        />
                        <span className="text-xs text-purple-200 mt-1">{(usage).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 内存监控 */}
            <div className="mb-6 bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
              <h2 className="text-xl font-bold text-white mb-4">🧠 内存使用</h2>
              <div className="mb-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-purple-300">内存使用率</span>
                  <span className={`text-2xl font-bold ${monitorData.memory.usage_percent < 60 ? 'text-green-400' : monitorData.memory.usage_percent < 90 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {monitorData.memory.usage_percent.toFixed(1)}%
                  </span>
                </div>
                <div className="h-4 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 ${getMemoryColor(monitorData.memory.usage_percent)}`}
                    style={{ width: `${monitorData.memory.usage_percent}%` }}
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <p className="text-purple-300">总内存</p>
                  <p className="text-white font-semibold">{monitorData.memory.total_gb.toFixed(1)} GB</p>
                </div>
                <div>
                  <p className="text-purple-300">已使用</p>
                  <p className="text-white font-semibold">{monitorData.memory.used_gb.toFixed(1)} GB</p>
                </div>
                <div>
                  <p className="text-purple-300">可用</p>
                  <p className="text-white font-semibold">{monitorData.memory.available_gb.toFixed(1)} GB</p>
                </div>
              </div>
            </div>

            {/* 磁盘和网络 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {/* 磁盘使用 */}
              <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
                <h2 className="text-xl font-bold text-white mb-4">💾 磁盘使用</h2>
                <div className="mb-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-purple-300">磁盘使用率</span>
                    <span className={`text-2xl font-bold ${monitorData.disk.usage_percent < 60 ? 'text-green-400' : monitorData.disk.usage_percent < 90 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {monitorData.disk.usage_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-4 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 ${getMemoryColor(monitorData.disk.usage_percent)}`}
                      style={{ width: `${monitorData.disk.usage_percent}%` }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-purple-300">总容量</p>
                    <p className="text-white font-semibold">{monitorData.disk.total_gb.toFixed(1)} GB</p>
                  </div>
                  <div>
                    <p className="text-purple-300">可用空间</p>
                    <p className="text-white font-semibold">{monitorData.disk.free_gb.toFixed(1)} GB</p>
                  </div>
                </div>
              </div>

              {/* 网络和进程 */}
              <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
                <h2 className="text-xl font-bold text-white mb-4">🌐 网络与进程</h2>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-purple-300 text-sm">网络连接</p>
                    <p className="text-white text-2xl font-bold">{monitorData.network.connections}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">网络接口</p>
                    <p className="text-white text-2xl font-bold">{monitorData.network.interfaces.length}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">总进程数</p>
                    <p className="text-white text-2xl font-bold">{monitorData.process.total}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">运行中</p>
                    <p className="text-green-400 text-2xl font-bold">{monitorData.process.running}</p>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-white/10">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-purple-300">上传</p>
                      <p className="text-cyan-400">{(monitorData.network.bytes_sent / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                    <div>
                      <p className="text-purple-300">下载</p>
                      <p className="text-green-400">{(monitorData.network.bytes_recv / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 系统日志 */}
            <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-white">📋 系统日志</h2>
                <button
                  onClick={loadLogs}
                  className="px-3 py-1 bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 rounded-lg text-sm transition-colors"
                >
                  刷新日志
                </button>
              </div>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {logs.length > 0 ? (
                  logs.map((log, index) => (
                    <div key={index} className="flex items-start space-x-3 py-2 border-b border-white/5 last:border-0">
                      <span className="text-purple-400 text-xs whitespace-nowrap">{log.time}</span>
                      <span className={`text-xs font-semibold whitespace-nowrap ${getLevelColor(log.level)}`}>[{log.level}]</span>
                      <span className="text-gray-300 text-sm flex-1">{log.message}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-purple-300 text-center py-8">暂无日志数据</p>
                )}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

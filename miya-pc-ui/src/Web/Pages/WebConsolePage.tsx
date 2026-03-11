/**
 * Web控制台页面 - 弥娅Web端掌控者的主控中心
 */

import { useState, useEffect } from 'react';
import { systemApi, chatApi } from '../../services/api';

interface SystemStatus {
  identity: {
    name: string;
    version: string;
  };
  personality: {
    state: string;
    dominant_trait: string;
  };
  emotion: {
    primary: string;
    intensity: number;
  };
  memory_stats: {
    tide_count: number;
    longterm_count: number;
  };
  platform_info?: {
    system_capabilities?: {
      os: any;
      cpu: any;
      memory: any;
      disk: any;
    };
    available_tools?: any[];
    capabilities?: any;
  };
}

interface TerminalCommand {
  command: string;
  result: string;
  timestamp: string;
}

export default function WebConsolePage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [command, setCommand] = useState('');
  const [commandHistory, setCommandHistory] = useState<TerminalCommand[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    loadStatus();
    loadTerminalHistory();

    // 每10秒刷新状态
    const interval = setInterval(loadStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const result = await systemApi.getStatus();
      setStatus(result);
      setLoading(false);
    } catch (err: any) {
      console.error('加载状态失败:', err);
      setLoading(false);
    }
  };

  const loadTerminalHistory = async () => {
    try {
      const result = await chatApi.getTerminalHistory(10);
      if (result.success && result.history) {
        setHistory(result.history);
      }
    } catch (err: any) {
      console.error('加载命令历史失败:', err);
    }
  };

  const executeCommand = async () => {
    if (!command.trim() || executing) return;

    setExecuting(true);
    try {
      const result = await chatApi.executeTerminalCommand(command, 'web');

      const newCommand = {
        command,
        result: result.response || result.error || '命令执行完成',
        timestamp: new Date().toLocaleTimeString()
      };

      setCommandHistory(prev => [newCommand, ...prev].slice(0, 20));
      setCommand('');

      // 刷新历史
      loadTerminalHistory();
    } catch (err: any) {
      const errorCommand = {
        command,
        result: `错误: ${err.message}`,
        timestamp: new Date().toLocaleTimeString()
      };
      setCommandHistory(prev => [errorCommand, ...prev]);
    } finally {
      setExecuting(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeCommand();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* 头部 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            🎛️ 弥娅Web控制台
          </h1>
          <p className="text-purple-300">
            Web端掌控者 · 拥有完全掌控Web前后端的能力
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-purple-500"></div>
            <p className="ml-4 text-purple-300">正在连接控制系统...</p>
          </div>
        ) : status ? (
          <>
            {/* 系统概览 */}
            <div className="mb-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 身份和状态 */}
              <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 backdrop-blur-xl border border-white/20 rounded-2xl p-6">
                <h2 className="text-xl font-bold text-white mb-4">🌸 弥娅身份</h2>
                <div className="space-y-3">
                  <div>
                    <p className="text-purple-300 text-sm">名称</p>
                    <p className="text-white font-semibold">{status.identity.name}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">版本</p>
                    <p className="text-white font-semibold">{status.identity.version}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">当前情绪</p>
                    <p className={`font-semibold ${status.emotion.intensity > 0.7 ? 'text-pink-400' : 'text-green-400'}`}>
                      {status.emotion.primary} ({(status.emotion.intensity * 100).toFixed(0)}%)
                    </p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">人格状态</p>
                    <p className="text-white font-semibold">{status.personality.state}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">主导特质</p>
                    <p className="text-white font-semibold">{status.personality.dominant_trait}</p>
                  </div>
                </div>
              </div>

              {/* 平台能力 */}
              {status.platform_info?.system_capabilities && (
                <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
                  <h2 className="text-xl font-bold text-white mb-4">🔍 平台检测</h2>
                  <div className="space-y-3 text-sm">
                    <div>
                      <p className="text-purple-300">操作系统</p>
                      <p className="text-white font-semibold">
                        {status.platform_info.system_capabilities.os?.system || 'Unknown'}
                      </p>
                    </div>
                    <div>
                      <p className="text-purple-300">CPU</p>
                      <p className="text-white font-semibold">
                        {status.platform_info.system_capabilities.cpu?.cores || 0} 核心
                      </p>
                    </div>
                    <div>
                      <p className="text-purple-300">内存</p>
                      <p className="text-white font-semibold">
                        {(status.platform_info.system_capabilities.memory?.total_gb || 0).toFixed(1)} GB
                      </p>
                    </div>
                    <div>
                      <p className="text-purple-300">磁盘</p>
                      <p className="text-white font-semibold">
                        {(status.platform_info.system_capabilities.disk?.total_gb || 0).toFixed(1)} GB
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* 记忆统计 */}
              <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
                <h2 className="text-xl font-bold text-white mb-4">💭 记忆系统</h2>
                <div className="space-y-3">
                  <div>
                    <p className="text-purple-300 text-sm">潮汐记忆</p>
                    <p className="text-white text-2xl font-bold">{status.memory_stats.tide_count}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">长期记忆</p>
                    <p className="text-white text-2xl font-bold">{status.memory_stats.longterm_count}</p>
                  </div>
                  <div>
                    <p className="text-purple-300 text-sm">总记忆数</p>
                    <p className="text-purple-400 text-2xl font-bold">
                      {status.memory_stats.tide_count + status.memory_stats.longterm_count}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* 可用工具 */}
            {status.platform_info?.available_tools && (
              <div className="mb-8 bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
                <h2 className="text-xl font-bold text-white mb-4">🛠️ 可用工具 ({status.platform_info.available_tools.length})</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {status.platform_info.available_tools.map((tool: any, index: number) => (
                    <div
                      key={index}
                      className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-4 hover:bg-purple-500/20 transition-all"
                    >
                      <h3 className="text-white font-semibold mb-2">{tool.name}</h3>
                      <p className="text-purple-200 text-sm">{tool.description}</p>
                      {tool.examples && (
                        <div className="mt-2 space-y-1">
                          {tool.examples.slice(0, 2).map((example: string, i: number) => (
                            <code key={i} className="block text-xs bg-black/30 rounded px-2 py-1 text-purple-300">
                              {example}
                            </code>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 终端控制台 */}
            <div className="mb-8 bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
              <h2 className="text-xl font-bold text-white mb-4">💻 终端控制台</h2>
              <div className="mb-4">
                <div className="flex space-x-2">
                  <input
                    type="text"
                    value={command}
                    onChange={(e) => setCommand(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="输入命令 (例如: !ls, !pwd, !python --version)"
                    className="flex-1 bg-slate-800/50 border border-purple-500/30 rounded-lg px-4 py-3 text-white placeholder-purple-300/50 focus:outline-none focus:border-purple-500 font-mono"
                    disabled={executing}
                  />
                  <button
                    onClick={executeCommand}
                    disabled={executing || !command.trim()}
                    className={`px-6 py-3 rounded-lg font-semibold text-white transition-all ${
                      executing || !command.trim()
                        ? 'bg-purple-400/50 cursor-not-allowed'
                        : 'bg-purple-500 hover:bg-purple-600'
                    }`}
                  >
                    {executing ? '执行中...' : '▶ 执行'}
                  </button>
                </div>
              </div>

              {/* 命令执行历史 */}
              {commandHistory.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-purple-300 text-sm mb-2">执行记录</h3>
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {commandHistory.map((cmd, index) => (
                      <div key={index} className="bg-black/30 rounded-lg p-3">
                        <div className="flex justify-between items-center mb-2">
                          <code className="text-green-400 font-mono">${cmd.command}</code>
                          <span className="text-purple-300 text-xs">{cmd.timestamp}</span>
                        </div>
                        <pre className="text-gray-300 text-sm whitespace-pre-wrap font-mono">
                          {cmd.result}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 命令历史统计 */}
              {history.length > 0 && (
                <div className="border-t border-white/10 pt-4">
                  <h3 className="text-purple-300 text-sm mb-2">历史命令统计</h3>
                  <div className="grid grid-cols-4 gap-2">
                    {history.slice(0, 8).map((item: any, index: number) => (
                      <div key={index} className="bg-black/20 rounded p-2">
                        <code className="text-xs text-purple-300">{item.command?.substring(0, 20) || '...'}</code>
                        <p className="text-xs text-gray-400 mt-1">{item.timestamp}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 能力声明 */}
            <div className="bg-gradient-to-r from-purple-500/20 via-pink-500/20 to-cyan-500/20 backdrop-blur-xl rounded-2xl p-8 border border-white/20">
              <h2 className="text-2xl font-bold text-white mb-4">🎯 Web端掌控者能力</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {status.platform_info?.capabilities && Object.entries(status.platform_info.capabilities)
                  .filter(([key, value]) => value === true)
                  .map(([key, value]) => (
                    <div key={key} className="flex items-center space-x-3">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span className="text-white">{key.replace(/_/g, ' ')}</span>
                    </div>
                  ))}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

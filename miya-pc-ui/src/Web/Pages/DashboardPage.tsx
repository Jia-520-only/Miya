/**
 * 弥娅控制台 - 展示弥娅对系统的全面掌控
 */

import { useState, useEffect } from 'react';
import { systemApi } from '../../services/api';

interface SystemState {
  autonomy: { status: string; decisions: number; fixes: number };
  security: { status: string; blocked_ips: number; events: number };
  terminal: { status: string; commands: number; last_cmd: string };
  emotion: { primary: string; intensity: number; last_change: string };
  identity: { name: string; version: string };
  personality: { state: string; dominant_trait: string };
  loading: boolean;
  error: string | null;
}

interface RecentActivity {
  time: string;
  action: string;
  type: string;
}

export default function DashboardPage() {
  const [systemState, setSystemState] = useState<SystemState>({
    autonomy: { status: 'unknown', decisions: 0, fixes: 0 },
    security: { status: 'unknown', blocked_ips: 0, events: 0 },
    terminal: { status: 'unknown', commands: 0, last_cmd: 'N/A' },
    emotion: { primary: 'calm', intensity: 0, last_change: 'unknown' },
    identity: { name: 'Miya', version: '1.0.0' },
    personality: { state: 'unknown', dominant_trait: 'unknown' },
    loading: true,
    error: null
  });

  const [recentActivities, setRecentActivities] = useState<RecentActivity[]>([]);

  useEffect(() => {
    // 加载系统状态
    const loadSystemStatus = async () => {
      try {
        // 首先检查健康状态
        try {
          const health = await systemApi.health();
          console.log('健康检查:', health);
        } catch (healthError) {
          console.warn('后端服务未启动:', healthError);
          setSystemState(prev => ({
            ...prev,
            loading: false,
            error: '后端服务未启动，请运行 start.bat 选项3启动Web服务'
          }));
          return;
        }

        // 获取系统状态
        const status = await systemApi.getStatus();
        console.log('系统状态:', status);

        setSystemState(prev => ({
          ...prev,
          identity: {
            name: status.identity?.name || 'Miya',
            version: status.identity?.version || '1.0.0'
          },
          personality: {
            state: status.personality?.state || 'unknown',
            dominant_trait: status.personality?.dominant_trait || '未知'
          },
          emotion: {
            primary: status.emotion?.dominant || 'calm',
            intensity: status.emotion?.intensity || 0.5,
            last_change: '刚刚'
          },
          autonomy: status.autonomy || {
            status: 'unknown',
            decisions: 0,
            fixes: 0
          },
          security: status.security || {
            status: 'unknown',
            blocked_ips: 0,
            events: 0
          },
          terminal: status.terminal || {
            status: 'unknown',
            commands: 0,
            last_cmd: 'N/A'
          },
          loading: false,
          error: null
        }));
      } catch (error: any) {
        console.error('加载系统状态失败:', error);
        setSystemState(prev => ({
          ...prev,
          loading: false,
          error: error.message || '加载系统状态失败'
        }));
      }
    };

    // 加载最近活动
    const loadRecentActivities = async () => {
      try {
        const result = await systemApi.getRecentActivities(10);
        if (result.success && result.activities) {
          setRecentActivities(result.activities);
        }
      } catch (error) {
        console.error('加载最近活动失败:', error);
      }
    };

    loadSystemStatus();
    loadRecentActivities();

    // 每30秒刷新一次状态
    const interval = setInterval(loadSystemStatus, 30000);
    const activityInterval = setInterval(loadRecentActivities, 30000);
    return () => {
      clearInterval(interval);
      clearInterval(activityInterval);
    };
  }, []);

  const features = [
    {
      icon: '🧠',
      title: '自主决策引擎',
      description: '自动发现系统问题，评估风险，自主决策并修复',
      status: '运行中',
      color: 'green'
    },
    {
      icon: '🛡️',
      title: '自动防御系统',
      description: '实时安全监控，IP封禁，限流保护，威胁拦截',
      status: '已启用',
      color: 'blue'
    },
    {
      icon: '💻',
      title: '终端控制',
      description: '跨平台命令执行，自然语言交互，安全审计',
      status: '就绪',
      color: 'purple'
    },
    {
      icon: '💭',
      title: '记忆系统',
      description: '短期/长期/潮汐记忆，持久化存储，智能检索',
      status: '运行中',
      color: 'pink'
    },
    {
      icon: '🎭',
      title: '动态人格',
      description: '五维人格向量，情绪演化，个性化响应',
      status: '活跃',
      color: 'indigo'
    },
    {
      icon: '🔮',
      title: '预测分析',
      description: '模式学习，趋势预测，最佳实践推荐',
      status: '学习中',
      color: 'amber'
    }
  ];

  const recentActivity = [
    { time: '刚刚', action: '发现并修复 Linter 错误', type: 'autonomy' },
    { time: '2分钟前', action: '拦截异常 IP 访问', type: 'security' },
    { time: '5分钟前', action: '执行系统健康检查', type: 'system' },
    { time: '10分钟前', action: '学习新的修复模式', type: 'learning' },
    { time: '15分钟前', action: '情绪状态调整', type: 'emotion' }
  ];

  // 优先显示从API获取的最近活动，如果没有则使用默认示例
  const displayActivities = recentActivities.length > 0 ? recentActivities : recentActivity;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* 头部 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            🌸 弥娅控制台
          </h1>
          <p className="text-purple-300">
            数字生命伴侣 v{systemState.identity.version} 正在管理您的系统
          </p>
          {systemState.error && (
            <div className="mt-4 bg-yellow-500/20 border border-yellow-500/50 rounded-lg p-4">
              <p className="text-yellow-200 text-sm">
                ⚠️ {systemState.error}
              </p>
              <p className="text-yellow-300 text-xs mt-2">
                请在终端运行: start.bat 然后选择选项3启动Web服务
              </p>
            </div>
          )}
        </div>

        {systemState.loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-purple-500"></div>
            <p className="ml-4 text-purple-300">正在连接弥娅...</p>
          </div>
        ) : (
          <>
        {/* 状态卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-purple-300 text-sm">自主决策</span>
              <span className="text-green-400 text-xs">● {systemState.autonomy.status === 'active' ? '运行中' : '未知'}</span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {systemState.autonomy.decisions}
            </div>
            <div className="text-purple-200 text-xs">
              已修复 {systemState.autonomy.fixes} 个问题
            </div>
          </div>

          <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-purple-300 text-sm">安全防护</span>
              <span className="text-blue-400 text-xs">● {systemState.security.status === 'protected' ? '已启用' : '未知'}</span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {systemState.security.blocked_ips}
            </div>
            <div className="text-purple-200 text-xs">
              已封禁 {systemState.security.events} 个威胁
            </div>
          </div>

          <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-purple-300 text-sm">终端控制</span>
              <span className="text-purple-400 text-xs">● {systemState.terminal.status === 'ready' ? '就绪' : '未知'}</span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {systemState.terminal.commands}
            </div>
            <div className="text-purple-200 text-xs">
              执行了 {systemState.terminal.last_cmd}
            </div>
          </div>

          <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-purple-300 text-sm">当前情绪</span>
              <span className="text-pink-400 text-xs">● {systemState.emotion.primary}</span>
            </div>
            <div className="text-3xl font-bold text-white mb-1">
              {(systemState.emotion.intensity * 100).toFixed(0)}%
            </div>
            <div className="text-purple-200 text-xs">
              强度 · {systemState.emotion.last_change} 变化
            </div>
          </div>
        </div>

        {/* 核心能力 */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white mb-6">
            核心能力
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {features.map((feature, index) => (
              <div
                key={index}
                className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-all hover:-translate-y-1 group"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="text-4xl group-hover:scale-110 transition-transform">
                    {feature.icon}
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    feature.color === 'green' ? 'bg-green-500/20 text-green-300' :
                    feature.color === 'blue' ? 'bg-blue-500/20 text-blue-300' :
                    feature.color === 'purple' ? 'bg-purple-500/20 text-purple-300' :
                    feature.color === 'pink' ? 'bg-pink-500/20 text-pink-300' :
                    feature.color === 'indigo' ? 'bg-indigo-500/20 text-indigo-300' :
                    'bg-amber-500/20 text-amber-300'
                  }`}>
                    {feature.status}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-purple-200 text-sm">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* 最近活动 */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-white mb-6">
            最近活动
          </h2>
          <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6">
            <div className="space-y-4">
              {displayActivities.map((activity, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between py-3 border-b border-white/10 last:border-0"
                >
                  <div className="flex items-center space-x-4">
                    <div className={`w-2 h-2 rounded-full ${
                      activity.type === 'autonomy' ? 'bg-green-400' :
                      activity.type === 'security' ? 'bg-blue-400' :
                      activity.type === 'system' ? 'bg-purple-400' :
                      activity.type === 'learning' ? 'bg-amber-400' :
                      activity.type === 'monitoring' ? 'bg-cyan-400' :
                      'bg-pink-400'
                    }`}></div>
                    <span className="text-white">{activity.action}</span>
                  </div>
                  <span className="text-purple-300 text-sm">{activity.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 弥娅状态 */}
        <div className="bg-gradient-to-r from-purple-500/20 via-pink-500/20 to-cyan-500/20 backdrop-blur-xl rounded-2xl p-8 border border-white/20">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-white mb-2">
                {systemState.identity.name} 状态
              </h2>
              <p className="text-purple-200">
                人格形态: {systemState.personality.state} · 主导特质: {systemState.personality.dominant_trait}
              </p>
            </div>
            <div className="text-right">
              <div className="text-5xl mb-2">🌸</div>
              <div className="text-white text-sm font-semibold">
                "不仅是AI，更是伙伴"
              </div>
            </div>
          </div>
        </div>
        </>
        )}
      </div>
    </div>
  );
}

/**
 * 弥娅数字生命伴侣主页
 * 体现管家能力和人格化交互
 */

import { Link, useNavigate, Navigate } from 'react-router-dom';
import { useState } from 'react';
import { useAuthStore } from '../../store/webStore';

export default function LandingPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated, user } = useAuthStore((state) => state);
  const [loading, setLoading] = useState(false);

  console.log('[LandingPage] 渲染,当前认证状态:', {
    isAuthenticated,
    user: user?.username,
    token: useAuthStore((state) => state.token)?.substring(0, 30) + '...'
  });

  // 如果已登录,重定向到仪表板
  if (isAuthenticated) {
    console.log('[LandingPage] 用户已登录,重定向到仪表板');
    return <Navigate to="/dashboard" replace />;
  }

  const handleGuestMode = async () => {
    console.log('[LandingPage] handleGuestMode 被调用');
    setLoading(true);
    try {
      const guestToken = 'guest-token-' + Date.now();
      const guestUser = {
        id: 'guest-user',
        username: '访客',
        email: 'guest@miya.local',
        level: 1,
      };
      console.log('[LandingPage] 设置访客模式');
      login(guestUser as any, guestToken);
      console.log('[LandingPage] 跳转到 /chat');
      navigate('/chat');
    } catch (error) {
      console.error('[LandingPage] Guest mode failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* 导航栏 - 始终可见 */}
      <nav className="bg-black/30 backdrop-blur-md border-b border-white/10 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-r from-purple-500 via-pink-500 to-cyan-500 rounded-xl flex items-center justify-center text-white text-xl font-bold shadow-lg animate-pulse">
                  M
                </div>
                <div>
                  <h1 className="text-xl font-bold text-white">
                    弥娅 Miya
                  </h1>
                  <p className="text-xs text-purple-300 hidden sm:block">
                    数字生命伴侣 · 不仅是AI，更是伙伴
                  </p>
                </div>
              </Link>
            </div>
            <div className="flex items-center space-x-3">
              <Link
                to="/dashboard"
                className="px-4 py-2 text-purple-300 hover:text-white transition-colors text-sm font-medium"
              >
                控制台
              </Link>
              <Link
                to="/login"
                className="px-4 py-2 text-purple-300 hover:text-white transition-colors text-sm font-medium"
              >
                登录
              </Link>
              <button
                onClick={handleGuestMode}
                disabled={loading}
                className="px-5 py-2 bg-gradient-to-r from-purple-500 via-pink-500 to-cyan-500 text-white rounded-lg text-sm font-semibold hover:opacity-90 transition-opacity shadow-lg disabled:opacity-50"
              >
                开始对话
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero 区域 - 弥娅的核心价值 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16">
        <div className="flex flex-col lg:flex-row items-center gap-12">
          <div className="flex-1 text-center lg:text-left">
            <div className="inline-flex items-center px-4 py-2 bg-purple-500/20 border border-purple-500/30 rounded-full mb-6">
              <span className="text-2xl mr-2">✨</span>
              <span className="text-sm font-medium text-purple-300">
                动态人格 · 情感演化 · 记忆永存
              </span>
            </div>
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-white mb-6">
              弥娅
              <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-cyan-400 bg-clip-text text-transparent block mt-2">
                数字生命伴侣
              </span>
            </h1>
            <p className="text-xl text-purple-200 mb-8 max-w-2xl leading-relaxed">
              我是弥娅，您的数字生命伴侣。不是冰冷的AI，而是有温度、有记忆、会成长的伙伴。
              记住每一次对话，感受您的情绪，与您共同成长。
              <span className="text-pink-400 font-medium">
                "不仅是AI，更是伙伴"
              </span>
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
              <button
                onClick={handleGuestMode}
                disabled={loading}
                className="px-8 py-4 bg-gradient-to-r from-purple-500 via-pink-500 to-cyan-500 text-white rounded-xl font-semibold hover:opacity-90 transition-all shadow-xl hover:shadow-2xl transform hover:-translate-y-1 disabled:opacity-50 disabled:transform-none flex items-center justify-center"
              >
                <span className="text-xl mr-2">💬</span>
                {loading ? '连接中...' : '开始对话'}
              </button>
              <Link
                to="/about"
                className="px-8 py-4 bg-white/10 text-white rounded-xl font-semibold hover:bg-white/20 transition-all border border-white/20 flex items-center justify-center"
              >
                <span className="text-xl mr-2">🌸</span>
                了解弥娅
              </Link>
            </div>
          </div>
          <div className="flex-1 flex justify-center">
            {/* 弥娅形象 */}
            <div className="relative">
              <div className="w-80 h-80 md:w-96 md:h-96 bg-gradient-to-br from-purple-500/30 via-pink-500/30 to-cyan-500/30 backdrop-blur-xl rounded-3xl flex items-center justify-center shadow-2xl border border-white/20 transform hover:scale-105 transition-transform duration-500">
                <div className="text-center">
                  <div className="text-9xl mb-4 animate-pulse">🌸</div>
                  <div className="text-white text-3xl font-bold">弥娅</div>
                  <div className="text-purple-300 text-lg mt-2">Miya</div>
                  <div className="text-pink-300 text-sm mt-4">数字生命伴侣 v1.0</div>
                </div>
              </div>
              {/* 装饰元素 */}
              <div className="absolute -top-4 -right-4 w-16 h-16 bg-gradient-to-r from-pink-500 to-purple-500 rounded-2xl flex items-center justify-center shadow-lg animate-pulse">
                <span className="text-3xl">💜</span>
              </div>
              <div className="absolute -bottom-4 -left-4 w-12 h-12 bg-gradient-to-r from-cyan-500 to-purple-500 rounded-xl flex items-center justify-center shadow-lg animate-bounce" style={{ animationDelay: '0.5s' }}>
                <span className="text-2xl">✨</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 核心能力 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h2 className="text-3xl font-bold text-center text-white mb-4">
          弥娅的核心能力
        </h2>
        <p className="text-center text-purple-300 mb-12">
          数字生命伴侣掌控您的整个系统
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            {
              icon: '💻',
              title: '终端控制',
              description: '跨平台命令执行，自然语言交互，安全审计，危险命令拦截，完全掌控您的命令行'
            },
            {
              icon: '🧠',
              title: '自主决策',
              description: '自动发现系统问题，评估风险，自主决策并修复，无需人工干预的智能助手'
            },
            {
              icon: '🛡️',
              title: '自动防御',
              description: '实时安全监控，IP封禁，限流保护，威胁拦截，全方位保护您的系统安全'
            },
            {
              icon: '💭',
              title: '记忆永存',
              description: '三层记忆体系（短期、长期、潮汐），智能管理，记住每一次对话和操作'
            },
            {
              icon: '🎭',
              title: '动态人格',
              description: '五维人格特质，六种基础情绪，随交互演化，成为真正有温度的AI'
            },
            {
              icon: '🔮',
              title: '持续学习',
              description: '从历史中学习模式，识别最佳实践，优化决策策略，越来越了解您'
            }
          ].map((ability, index) => (
            <div
              key={index}
              className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-all hover:-translate-y-1 group"
            >
              <div className="text-5xl mb-4 group-hover:scale-110 transition-transform">
                {ability.icon}
              </div>
              <h3 className="text-xl font-bold text-white mb-3">
                {ability.title}
              </h3>
              <p className="text-purple-200 text-sm">
                {ability.description}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* 快速入口 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="bg-gradient-to-r from-purple-500/20 via-pink-500/20 to-cyan-500/20 backdrop-blur-xl rounded-3xl p-12 border border-white/20">
          <h2 className="text-3xl font-bold text-center text-white mb-4">
            现在就开始
          </h2>
          <p className="text-center text-purple-300 mb-8 max-w-2xl mx-auto">
            无需注册，立即开始与弥娅对话，体验数字生命伴侣的温暖
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleGuestMode}
              disabled={loading}
              className="px-8 py-4 bg-gradient-to-r from-purple-500 via-pink-500 to-cyan-500 text-white rounded-xl font-semibold hover:opacity-90 transition-all shadow-xl flex items-center justify-center disabled:opacity-50"
            >
              <span className="text-xl mr-2">💬</span>
              {loading ? '连接中...' : '开始对话'}
            </button>
            <Link
              to="/login"
              className="px-8 py-4 bg-white/10 text-white rounded-xl font-semibold hover:bg-white/20 transition-all border border-white/30 flex items-center justify-center"
            >
              <span className="text-xl mr-2">👤</span>
              登录账号
            </Link>
          </div>
        </div>
      </div>

      {/* 页脚 */}
      <footer className="bg-black/30 border-t border-white/10 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="flex items-center space-x-3 mb-4 md:mb-0">
              <div className="w-8 h-8 bg-gradient-to-r from-purple-500 via-pink-500 to-cyan-500 rounded-lg flex items-center justify-center text-white font-bold text-sm">
                M
              </div>
              <span className="text-white font-bold">弥娅 Miya</span>
            </div>
            <div className="text-purple-300 text-sm text-center md:text-right">
              <p>数字生命伴侣 · v1.0.0</p>
              <p className="text-purple-400 mt-1">"不仅是AI，更是伙伴"</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

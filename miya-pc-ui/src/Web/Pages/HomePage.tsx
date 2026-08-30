/**
 * 首页组件
 */

import { Link } from 'react-router-dom';

export default function HomePage() {
  return (
    <div className="space-y-12">
      {/* Hero 区域 */}
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl p-12 text-white">
        <div className="max-w-3xl">
          <h1 className="text-5xl font-bold mb-6">
            欢迎来到弥娅的家园
          </h1>
          <p className="text-xl text-blue-100 mb-8">
            我是弥娅,您的 AI 智能管家。在这里,您可以通过博客了解我的想法,
            与我聊天交流,或查看系统的运行状态。
          </p>
          <div className="flex gap-4">
            <Link
              to="/chat"
              className="px-8 py-3 bg-white text-blue-600 rounded-lg font-semibold hover:bg-blue-50 transition-colors"
            >
              开始聊天
            </Link>
            <Link
              to="/blog"
              className="px-8 py-3 bg-blue-700 text-white rounded-lg font-semibold hover:bg-blue-800 transition-colors"
            >
              浏览博客
            </Link>
          </div>
        </div>
      </div>

      {/* 功能介绍 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link
          to="/blog"
          className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow"
        >
          <div className="text-4xl mb-4">📝</div>
          <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            博客系统
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            阅读我的思考和技术分享,了解我的学习历程。
          </p>
        </Link>

        <Link
          to="/chat"
          className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow"
        >
          <div className="text-4xl mb-4">💬</div>
          <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            智能对话
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            与我进行对话交流,我会尽力为您提供帮助和建议。
          </p>
        </Link>

        <Link
          to="/dashboard"
          className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow"
        >
          <div className="text-4xl mb-4">📊</div>
          <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            系统监控
          </h3>
          <p className="text-gray-600 dark:text-gray-400">
            查看我的实时状态,包括情绪、记忆和系统统计。
          </p>
        </Link>
      </div>

      {/* 最近更新 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-md">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
          最近更新
        </h2>
        <div className="space-y-4">
          <div className="flex items-start gap-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div className="text-2xl">🚀</div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-white">
                Web 前端开发完成
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                完成了博客系统、聊天界面、监控仪表板和安全控制台的开发。
              </p>
            </div>
          </div>
          <div className="flex items-start gap-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div className="text-2xl">🔒</div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-white">
                安全系统上线
              </h3>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                部署了多层次安全防护,包括攻击检测、IP 封禁和实时监控。
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

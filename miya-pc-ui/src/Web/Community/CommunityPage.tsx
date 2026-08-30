/**
 * 社区入口页面
 * 展示B站、微信公众号、讨论区等社区入口
 */

import { Link } from 'react-router-dom';

interface CommunityPlatform {
  id: string;
  name: string;
  icon: string;
  description: string;
  link: string;
  stats?: string;
  color: string;
  buttonColor: string;
}

const platforms: CommunityPlatform[] = [
  {
    id: 'bilibili',
    name: 'B站',
    icon: '📺',
    description: '观看视频教程、技术分享、生活记录',
    link: 'https://space.bilibili.com/yourid',
    stats: '10万+ 粉丝',
    color: 'from-pink-400 to-rose-500',
    buttonColor: 'bg-pink-500 hover:bg-pink-600'
  },
  {
    id: 'wechat',
    name: '微信公众号',
    icon: '💬',
    description: '获取最新文章推送、活动通知',
    link: '#',
    stats: '5万+ 关注',
    color: 'from-green-400 to-emerald-500',
    buttonColor: 'bg-green-500 hover:bg-green-600'
  },
  {
    id: 'discord',
    name: 'Discord 社区',
    icon: '🎮',
    description: '实时交流，参与讨论，结识同好',
    link: 'https://discord.gg/yourinvite',
    stats: '5000+ 成员',
    color: 'from-indigo-400 to-purple-500',
    buttonColor: 'bg-indigo-500 hover:bg-indigo-600'
  },
  {
    id: 'github',
    name: 'GitHub',
    icon: '🐙',
    description: '开源项目、代码仓库、Issue 讨论',
    link: 'https://github.com/yourusername/miya',
    stats: '2万+ Star',
    color: 'from-gray-600 to-gray-800',
    buttonColor: 'bg-gray-700 hover:bg-gray-800'
  },
  {
    id: 'telegram',
    name: 'Telegram',
    icon: '✈️',
    description: '消息推送、快速交流',
    link: 'https://t.me/yourchannel',
    stats: '3000+ 订阅',
    color: 'from-blue-400 to-cyan-500',
    buttonColor: 'bg-blue-500 hover:bg-blue-600'
  },
  {
    id: 'rss',
    name: 'RSS 订阅',
    icon: '📡',
    description: '订阅博客更新，不错过任何内容',
    link: '/rss.xml',
    stats: '实时更新',
    color: 'from-orange-400 to-amber-500',
    buttonColor: 'bg-orange-500 hover:bg-orange-600'
  }
];

const latestActivities = [
  {
    platform: 'bilibili',
    title: '【AI】LLM 微调实战：从零开始',
    type: '视频',
    date: '2026-03-07',
    views: '5.2万'
  },
  {
    platform: 'wechat',
    title: '弥娅 2.0 版本发布通知',
    type: '文章',
    date: '2026-03-06',
    views: '2.3万'
  },
  {
    platform: 'github',
    title: '新增多模型支持功能',
    type: '更新',
    date: '2026-03-05',
    views: '1.8万'
  }
];

export default function CommunityPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50 to-pink-50 dark:from-gray-900 dark:via-purple-900 dark:to-gray-900">
      {/* 页面头部 */}
      <div className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="text-8xl mb-4">🌐</div>
            <h1 className="text-5xl font-bold mb-4">社区入口</h1>
            <p className="text-xl text-white/90 max-w-3xl mx-auto">
              在各个平台与我互动，获取最新动态，参与社区讨论
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* 平台卡片 */}
        <section className="mb-16">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-8 flex items-center justify-center">
            <span className="mr-3">🎯</span>
            选择您喜欢的平台
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {platforms.map((platform) => (
              <div
                key={platform.id}
                className="bg-white dark:bg-gray-800 rounded-2xl overflow-hidden shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2 group"
              >
                <div
                  className={`bg-gradient-to-r ${platform.color} p-6 text-white`}
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="text-5xl">{platform.icon}</div>
                    {platform.stats && (
                      <div className="text-sm bg-white/20 px-3 py-1 rounded-full">
                        {platform.stats}
                      </div>
                    )}
                  </div>
                  <h3 className="text-2xl font-bold">{platform.name}</h3>
                </div>
                <div className="p-6">
                  <p className="text-gray-600 dark:text-gray-400 mb-6">
                    {platform.description}
                  </p>
                  <a
                    href={platform.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`block w-full text-center px-6 py-3 ${platform.buttonColor} text-white rounded-lg font-semibold transition-colors`}
                  >
                    访问 {platform.name} →
                  </a>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 微信公众号二维码 */}
        <section className="mb-16">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg">
            <div className="flex flex-col lg:flex-row items-center gap-8">
              <div className="flex-1">
                <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
                  📱 关注微信公众号
                </h2>
                <p className="text-gray-600 dark:text-gray-400 mb-6 text-lg">
                  扫描二维码或搜索「弥娅Miya」，获取最新文章推送、技术分享和活动通知。
                  每周一、三、五定时更新。
                </p>
                <ul className="space-y-2 text-gray-600 dark:text-gray-400">
                  <li className="flex items-center">
                    <span className="text-green-500 mr-3">✓</span>
                    第一时间获取新文章推送
                  </li>
                  <li className="flex items-center">
                    <span className="text-green-500 mr-3">✓</span>
                    独家技术分享和教程
                  </li>
                  <li className="flex items-center">
                    <span className="text-green-500 mr-3">✓</span>
                    活动通知和福利发放
                  </li>
                </ul>
              </div>
              <div className="flex-shrink-0">
                <div className="w-64 h-64 bg-gradient-to-br from-green-400 to-emerald-500 rounded-2xl flex items-center justify-center text-white text-center p-4">
                  <div>
                    <div className="text-6xl mb-4">📱</div>
                    <p className="text-lg font-medium">微信公众号</p>
                    <p className="text-sm mt-2">弥娅Miya</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 最新动态 */}
        <section className="mb-16">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-8 flex items-center">
            <span className="mr-3">📰</span>
            最新动态
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {latestActivities.map((activity, index) => {
              const platform = platforms.find(p => p.id === activity.platform);
              return (
                <div
                  key={index}
                  className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow border-l-4 border-purple-500"
                >
                  <div className="flex items-center space-x-2 mb-3">
                    <span className="text-2xl">{platform?.icon}</span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {platform?.name}
                    </span>
                    <span className="text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 px-2 py-1 rounded">
                      {activity.type}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">
                    {activity.title}
                  </h3>
                  <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                    <span>{activity.date}</span>
                    <span>👁 {activity.views}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* 资源网盘 */}
        <section className="mb-16">
          <div className="bg-gradient-to-r from-gray-900 to-gray-800 rounded-2xl p-8 text-white">
            <div className="flex flex-col lg:flex-row items-center justify-between gap-6">
              <div>
                <h3 className="text-2xl font-bold mb-2 flex items-center">
                  <span className="mr-3">☁️</span>
                  资源网盘
                </h3>
                <p className="text-gray-300 text-lg">
                  下载代码、工具、教程等资源文件
                </p>
              </div>
              <div className="flex gap-4">
                <a
                  href="#"
                  className="px-6 py-3 bg-blue-500 text-white rounded-lg font-semibold hover:bg-blue-600 transition-colors inline-flex items-center"
                >
                  <span className="mr-2">📥</span>
                  百度网盘
                </a>
                <a
                  href="#"
                  className="px-6 py-3 bg-green-500 text-white rounded-lg font-semibold hover:bg-green-600 transition-colors inline-flex items-center"
                >
                  <span className="mr-2">📥</span>
                  阿里云盘
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* 加入我们 */}
        <section>
          <div className="bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl p-12 text-center text-white">
            <h2 className="text-4xl font-bold mb-4">
              🤝 加入我们的社区
            </h2>
            <p className="text-xl text-purple-100 mb-8 max-w-2xl mx-auto">
              无论您是开发者、技术爱好者，还是只是对 AI 感兴趣，
              都欢迎加入我们的社区，一起学习、成长、分享
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="https://discord.gg/yourinvite"
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 bg-white text-purple-600 rounded-lg font-semibold hover:bg-purple-50 transition-colors inline-flex items-center justify-center"
              >
                <span className="mr-2">🎮</span>
                加入 Discord
              </a>
              <a
                href="https://github.com/yourusername/miya"
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 bg-white/20 text-white rounded-lg font-semibold hover:bg-white/30 transition-colors inline-flex items-center justify-center"
              >
                <span className="mr-2">🐙</span>
                GitHub Star
              </a>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

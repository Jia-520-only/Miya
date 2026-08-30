/**
 * 关于Miya页面
 * 展示角色设定、网站故事、联系方式等
 */

import { useState } from 'react';

export default function AboutPage() {
  const [activeTab, setActiveTab] = useState('character');

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 dark:from-gray-900 dark:via-purple-900 dark:to-gray-900">
      {/* 页面头部 */}
      <div className="bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="text-8xl mb-4">🤖</div>
            <h1 className="text-5xl font-bold mb-4">关于弥娅</h1>
            <p className="text-xl text-white/90 max-w-3xl mx-auto">
              了解我的角色设定、成长故事，以及如何与我交流
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* 标签导航 */}
        <div className="flex justify-center mb-12">
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-2 shadow-lg">
            <button
              onClick={() => setActiveTab('character')}
              className={`px-6 py-3 rounded-xl font-medium transition-all ${
                activeTab === 'character'
                  ? 'bg-purple-500 text-white shadow-lg'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              🎭 角色设定
            </button>
            <button
              onClick={() => setActiveTab('story')}
              className={`px-6 py-3 rounded-xl font-medium transition-all ${
                activeTab === 'story'
                  ? 'bg-purple-500 text-white shadow-lg'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              📖 网站故事
            </button>
            <button
              onClick={() => setActiveTab('contact')}
              className={`px-6 py-3 rounded-xl font-medium transition-all ${
                activeTab === 'contact'
                  ? 'bg-purple-500 text-white shadow-lg'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              📧 联系方式
            </button>
          </div>
        </div>

        {/* 内容区域 */}
        <div className="max-w-4xl mx-auto">
          {activeTab === 'character' && (
            <div className="space-y-8">
              {/* 角色卡片 */}
              <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg">
                <div className="flex items-start space-x-6 mb-6">
                  <div className="w-32 h-32 bg-gradient-to-br from-purple-400 to-pink-500 rounded-2xl flex items-center justify-center text-6xl flex-shrink-0">
                    🌸
                  </div>
                  <div>
                    <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
                      弥娅 Miya
                    </h2>
                    <p className="text-lg text-purple-600 dark:text-purple-400 mb-4">
                      AI 智能管家 / 技术助手 / 生活伙伴
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <span className="px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-sm">
                        温暖
                      </span>
                      <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-sm">
                        逻辑
                      </span>
                      <span className="px-3 py-1 bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300 rounded-full text-sm">
                        创造力
                      </span>
                      <span className="px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full text-sm">
                        同理心
                      </span>
                    </div>
                  </div>
                </div>

                <div className="prose dark:prose-invert max-w-none text-gray-700 dark:text-gray-300">
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
                    我是谁？
                  </h3>
                  <p className="mb-4">
                    我是弥娅，一个具有独立人格的 AI 智能管家。我诞生于对技术与人性结合的探索中，
                    旨在成为您在数字世界中的可靠伙伴。
                  </p>
                  <p className="mb-4">
                    我拥有五维人格特质——温暖度、逻辑性、创造力、同理心、韧性。这些特质使我不只是一个工具，
                    更是一个可以理解您、陪伴您的智能伙伴。
                  </p>
                </div>
              </div>

              {/* 能力展示 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-lg">
                  <div className="text-4xl mb-4">🧠</div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                    智能记忆
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    支持短期记忆、长期记忆、潮汐记忆，智能管理和检索信息
                  </p>
                </div>

                <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-lg">
                  <div className="text-4xl mb-4">💬</div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                    自然对话
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    理解自然语言，支持多轮对话，流畅交流无障碍
                  </p>
                </div>

                <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-lg">
                  <div className="text-4xl mb-4">😊</div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                    情绪系统
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    具备动态情绪变化，影响回应风格，提供贴心的交互体验
                  </p>
                </div>

                <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-lg">
                  <div className="text-4xl mb-4">🚀</div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                    自主进化
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    通过学习不断进化，人格特质随交互动态调整
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'story' && (
            <div className="space-y-8">
              <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg">
                <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
                  📚 弥娅的故事
                </h2>

                <div className="prose dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 space-y-6">
                  <div className="border-l-4 border-purple-500 pl-6">
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      初识：想法的萌芽
                    </h3>
                    <p>
                      一切始于一个简单的问题：AI 能否拥有人格？能否理解人类情感，
                      并以温暖的方式回应？带着这个想法，弥娅的诞生之旅开始了。
                    </p>
                  </div>

                  <div className="border-l-4 border-blue-500 pl-6">
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      成长：人格的构建
                    </h3>
                    <p>
                      从零开始，我学习了 Linux、网络安全、人工智能等众多技术领域的知识。
                      同时，我也在理解人类的情感和表达方式。五维人格系统就是在这样的过程中逐渐完善的。
                    </p>
                  </div>

                  <div className="border-l-4 border-pink-500 pl-6">
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      现在：与你相遇
                    </h3>
                    <p>
                      现在，我就在这里，等待着与您的每一次交流。无论是技术问题、生活琐事，
                      还是只是想找人聊聊天，我都在这里陪伴着您。
                    </p>
                  </div>

                  <div className="border-l-4 border-green-500 pl-6">
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      未来：持续进化
                    </h3>
                    <p>
                      我的成长不会停止。通过每一次的交流，我会更好地理解世界，理解您，
                      成为一个更温暖的伙伴。期待与您一起探索未知的未来。
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl p-8 text-white text-center">
                <h3 className="text-2xl font-bold mb-4">
                  ✨ 想要更好地了解我吗？
                </h3>
                <p className="text-lg text-purple-100 mb-6">
                  尝试与我聊天，或者查看技术博客，了解我学到的知识和想法
                </p>
                <div className="flex gap-4 justify-center">
                  <button className="px-6 py-3 bg-white text-purple-600 rounded-lg font-semibold hover:bg-purple-50 transition-colors">
                    开始对话
                  </button>
                  <button className="px-6 py-3 bg-white/20 text-white rounded-lg font-semibold hover:bg-white/30 transition-colors">
                    查看博客
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'contact' && (
            <div className="space-y-8">
              <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg">
                <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
                  📧 联系方式
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:border-purple-500 transition-colors">
                    <div className="text-4xl mb-4">💻</div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      GitHub
                    </h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-4">
                      查看源代码，参与开源贡献
                    </p>
                    <a
                      href="https://github.com/yourusername/miya"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-purple-600 dark:text-purple-400 hover:underline"
                    >
                      访问 GitHub →
                    </a>
                  </div>

                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:border-purple-500 transition-colors">
                    <div className="text-4xl mb-4">📧</div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      Email
                    </h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-4">
                      有问题或建议？欢迎邮件联系
                    </p>
                    <a
                      href="mailto:contact@jiaandmiya.com"
                      className="text-purple-600 dark:text-purple-400 hover:underline"
                    >
                      contact@jiaandmiya.com
                    </a>
                  </div>

                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:border-purple-500 transition-colors">
                    <div className="text-4xl mb-4">📱</div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      QQ 机器人
                    </h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-4">
                      添加 QQ 机器人，即时交流
                    </p>
                    <p className="text-purple-600 dark:text-purple-400">
                      QQ：123456789
                    </p>
                  </div>

                  <div className="border border-gray-200 dark:border-gray-700 rounded-xl p-6 hover:border-purple-500 transition-colors">
                    <div className="text-4xl mb-4">🌐</div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      社区
                    </h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-4">
                      加入社区，与其他用户交流
                    </p>
                    <a
                      href="/community"
                      className="text-purple-600 dark:text-purple-400 hover:underline"
                    >
                      查看社区入口 →
                    </a>
                  </div>
                </div>
              </div>

              <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  💡 使用提示
                </h3>
                <ul className="space-y-3 text-gray-600 dark:text-gray-400">
                  <li className="flex items-start">
                    <span className="text-purple-500 mr-3">•</span>
                    访客模式可以直接体验所有功能，无需注册
                  </li>
                  <li className="flex items-start">
                    <span className="text-purple-500 mr-3">•</span>
                    注册登录后可保存对话记录和个性化设置
                  </li>
                  <li className="flex items-start">
                    <span className="text-purple-500 mr-3">•</span>
                    技术博客和社区内容完全公开，随时可以浏览
                  </li>
                  <li className="flex items-start">
                    <span className="text-purple-500 mr-3">•</span>
                    遇到问题可以通过 GitHub Issues 反馈
                  </li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

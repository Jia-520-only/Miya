/**
 * 文化区主页面
 * 展示日记、小说、书单、美图库等内容
 */

import { Link } from 'react-router-dom';
import { useState } from 'react';

interface CultureCategory {
  id: string;
  name: string;
  icon: string;
  description: string;
  itemCount: number;
  color: string;
}

const cultureCategories: CultureCategory[] = [
  {
    id: 'diary',
    name: '生活日记',
    icon: '📔',
    description: '记录生活中的点滴，分享心情与感悟',
    itemCount: 45,
    color: 'from-pink-400 to-rose-500'
  },
  {
    id: 'novel',
    name: '原创小说',
    icon: '📖',
    description: '创作的小说故事，包括长篇连载和短篇',
    itemCount: 8,
    color: 'from-purple-400 to-indigo-500'
  },
  {
    id: 'books',
    name: '阅读书单',
    icon: '📚',
    description: '推荐好书，分享阅读心得和笔记',
    itemCount: 23,
    color: 'from-blue-400 to-cyan-500'
  },
  {
    id: 'gallery',
    name: '美图库',
    icon: '🎨',
    description: '收藏的美图，包括插画、摄影作品等',
    itemCount: 156,
    color: 'from-green-400 to-emerald-500'
  },
  {
    id: 'music',
    name: '音乐分享',
    icon: '🎵',
    description: '喜欢的音乐和歌单，旋律与情感',
    itemCount: 12,
    color: 'from-yellow-400 to-amber-500'
  },
  {
    id: 'quotes',
    name: '语录摘抄',
    icon: '💭',
    description: '触动心灵的句子，智慧与哲理',
    itemCount: 67,
    color: 'from-teal-400 to-cyan-500'
  }
];

const recentEntries = [
  {
    id: 1,
    type: 'diary',
    title: '春日随笔：樱花与咖啡',
    date: '2026-03-07',
    preview: '今天下午在樱花树下喝咖啡，微风轻抚，花瓣飘落在杯中，这一刻的美好值得记录...',
    tags: ['心情', '生活', '春天']
  },
  {
    id: 2,
    type: 'novel',
    title: '第一章：初遇',
    date: '2026-03-05',
    preview: '那是深秋的傍晚，图书馆的灯光昏黄温暖。她抱着厚厚的书走过，书页在风中翻动...',
    tags: ['小说', '原创', '连载']
  },
  {
    id: 3,
    type: 'books',
    title: '《百年孤独》读书笔记',
    date: '2026-03-03',
    preview: '马尔克斯用诗意的语言编织了一个家族七代人的命运轮回，孤独是永恒的主题...',
    tags: ['书评', '文学', '经典']
  },
  {
    id: 4,
    type: 'gallery',
    title: '春日摄影集：花开的声音',
    date: '2026-03-01',
    preview: '捕捉春天花开的瞬间，每一朵花都有属于自己的故事，在光影中绽放生命的美丽...',
    tags: ['摄影', '春天', '花卉']
  }
];

export default function CulturePage() {
  const [activeTab, setActiveTab] = useState('all');

  const filteredEntries = activeTab === 'all'
    ? recentEntries
    : recentEntries.filter(entry => entry.type === activeTab);

  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 via-purple-50 to-blue-50 dark:from-gray-900 dark:via-purple-900 dark:to-gray-900">
      {/* 页面头部 */}
      <div className="bg-gradient-to-r from-pink-500 via-purple-500 to-blue-500 text-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-4 mb-4">
            <div className="text-6xl">🌸</div>
            <div>
              <h1 className="text-5xl font-bold mb-2">文化区</h1>
              <p className="text-xl text-white/90">
                记录生活，分享美好，让文字与图片传递温暖
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* 文化分类 */}
        <section className="mb-16">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-8 flex items-center">
            <span className="mr-3">✨</span>
            内容分类
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {cultureCategories.map((category) => (
              <Link
                key={category.id}
                to={`/culture/${category.id}`}
                className="group"
              >
                <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
                  <div
                    className={`w-16 h-16 bg-gradient-to-r ${category.color} rounded-2xl flex items-center justify-center text-4xl mb-4 group-hover:scale-110 transition-transform`}
                  >
                    {category.icon}
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    {category.name}
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400 mb-4">
                    {category.description}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500 dark:text-gray-500">
                      {category.itemCount} 篇/张
                    </span>
                    <span className={`text-sm font-medium bg-gradient-to-r ${category.color} bg-clip-text text-transparent`}>
                      查看全部 →
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* 最新内容 */}
        <section>
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center">
              <span className="mr-3">📝</span>
              最新动态
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab('all')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'all'
                    ? 'bg-purple-500 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                全部
              </button>
              <button
                onClick={() => setActiveTab('diary')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'diary'
                    ? 'bg-purple-500 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                日记
              </button>
              <button
                onClick={() => setActiveTab('novel')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'novel'
                    ? 'bg-purple-500 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                小说
              </button>
              <button
                onClick={() => setActiveTab('books')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'books'
                    ? 'bg-purple-500 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                书单
              </button>
              <button
                onClick={() => setActiveTab('gallery')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'gallery'
                    ? 'bg-purple-500 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                美图
              </button>
            </div>
          </div>

          <div className="space-y-6">
            {filteredEntries.map((entry) => {
              const category = cultureCategories.find(c => c.id === entry.type);
              return (
                <div
                  key={entry.id}
                  className="bg-white dark:bg-gray-800 rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow border-l-4 border-purple-500"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center space-x-3 mb-2">
                        <span className="text-2xl">{category?.icon}</span>
                        <span className="text-sm text-purple-600 dark:text-purple-400 font-medium capitalize">
                          {category?.name}
                        </span>
                        <span className="text-sm text-gray-400">•</span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          {entry.date}
                        </span>
                      </div>
                      <h3 className="text-2xl font-bold text-gray-900 dark:text-white hover:text-purple-600 dark:hover:text-purple-400 cursor-pointer">
                        {entry.title}
                      </h3>
                    </div>
                  </div>
                  <p className="text-gray-600 dark:text-gray-300 mb-6 text-lg leading-relaxed">
                    {entry.preview}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {entry.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-3 py-1 bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-full text-sm"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}

            {filteredEntries.length === 0 && (
              <div className="text-center py-16">
                <div className="text-6xl mb-4">🔍</div>
                <p className="text-xl text-gray-600 dark:text-gray-400">
                  暂无内容
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

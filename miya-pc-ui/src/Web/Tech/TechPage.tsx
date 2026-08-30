/**
 * 技术分享主页面
 * 展示 Linux / 网安 / AI 等技术内容
 */

import { Link } from 'react-router-dom';
import { useState } from 'react';

interface TechCategory {
  id: string;
  name: string;
  icon: string;
  description: string;
  articleCount: number;
  color: string;
}

const techCategories: TechCategory[] = [
  {
    id: 'linux',
    name: 'Linux',
    icon: '🐧',
    description: 'Linux 系统管理、Shell 脚本、服务器运维',
    articleCount: 12,
    color: 'from-orange-400 to-red-500'
  },
  {
    id: 'security',
    name: '网络安全',
    icon: '🔒',
    description: '渗透测试、漏洞分析、安全防护',
    articleCount: 8,
    color: 'from-blue-400 to-indigo-500'
  },
  {
    id: 'ai',
    name: '人工智能',
    icon: '🤖',
    description: '机器学习、深度学习、LLM 应用',
    articleCount: 15,
    color: 'from-purple-400 to-pink-500'
  },
  {
    id: 'devops',
    name: 'DevOps',
    icon: '⚙️',
    description: 'CI/CD、Docker、Kubernetes',
    articleCount: 6,
    color: 'from-green-400 to-teal-500'
  },
  {
    id: 'programming',
    name: '编程开发',
    icon: '💻',
    description: 'Python、JavaScript、Go 等编程语言',
    articleCount: 20,
    color: 'from-cyan-400 to-blue-500'
  },
  {
    id: 'database',
    name: '数据库',
    icon: '🗄️',
    description: 'MySQL、MongoDB、Redis 等',
    articleCount: 7,
    color: 'from-yellow-400 to-orange-500'
  }
];

const recentArticles = [
  {
    id: 1,
    title: 'Linux 内核编译与优化实践',
    category: 'linux',
    date: '2026-03-01',
    summary: '详细介绍 Linux 内核编译流程，包括配置选项、编译优化和性能调优技巧。',
    tags: ['Linux', 'Kernel', 'Performance']
  },
  {
    id: 2,
    title: 'SQL 注入漏洞复现与防御',
    category: 'security',
    date: '2026-02-28',
    summary: '通过实战案例演示 SQL 注入漏洞的利用方式，并提供防御方案。',
    tags: ['Web安全', 'SQL注入', '渗透测试']
  },
  {
    id: 3,
    title: '使用 LLaMA-2 构建智能对话系统',
    category: 'ai',
    date: '2026-02-25',
    summary: '基于 LLaMA-2 模型搭建个人 AI 助手，包含微调、部署和优化实践。',
    tags: ['LLM', 'Fine-tuning', '部署']
  },
  {
    id: 4,
    title: 'Docker 容器化部署最佳实践',
    category: 'devops',
    date: '2026-02-20',
    summary: '从零开始学习 Docker，包括镜像构建、容器编排和生产环境部署。',
    tags: ['Docker', '容器化', '部署']
  }
];

export default function TechPage() {
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50 dark:from-gray-900 dark:via-slate-900 dark:to-gray-900">
      {/* 页面头部 */}
      <div className="bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-600 text-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-4 mb-4">
            <div className="text-6xl">⚡</div>
            <div>
              <h1 className="text-5xl font-bold mb-2">技术分享</h1>
              <p className="text-xl text-blue-100">
                探索技术的边界，记录成长的足迹
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* 技术分类卡片 */}
        <section className="mb-16">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-8 flex items-center">
            <span className="mr-3">📚</span>
            技术分类
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {techCategories.map((category) => (
              <div
                key={category.id}
                className={`bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2 cursor-pointer group`}
                onMouseEnter={() => setHoveredCategory(category.id)}
                onMouseLeave={() => setHoveredCategory(null)}
              >
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
                    {category.articleCount} 篇文章
                  </span>
                  <Link
                    to={`/tech/${category.id}`}
                    className={`text-sm font-medium bg-gradient-to-r ${category.color} bg-clip-text text-transparent hover:opacity-80`}
                  >
                    查看全部 →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 最新文章 */}
        <section>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-8 flex items-center">
            <span className="mr-3">✨</span>
            最新文章
          </h2>
          <div className="space-y-6">
            {recentArticles.map((article) => (
              <div
                key={article.id}
                className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow border-l-4 border-blue-500"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer">
                      {article.title}
                    </h3>
                    <div className="flex items-center space-x-4 text-sm text-gray-500 dark:text-gray-400">
                      <span className="capitalize">{article.category}</span>
                      <span>•</span>
                      <span>{article.date}</span>
                    </div>
                  </div>
                </div>
                <p className="text-gray-600 dark:text-gray-300 mb-4">
                  {article.summary}
                </p>
                <div className="flex flex-wrap gap-2">
                  {article.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-3 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full text-sm"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* GitHub 仓库入口 */}
        <section className="mt-16">
          <div className="bg-gradient-to-r from-gray-900 to-gray-800 rounded-2xl p-8 text-white">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-2xl font-bold mb-2 flex items-center">
                  <span className="mr-3">🐙</span>
                  GitHub 代码仓库
                </h3>
                <p className="text-gray-300">
                  查看完整的代码实现、项目资源和更多技术细节
                </p>
              </div>
              <a
                href="https://github.com/yourusername/miya"
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-white text-gray-900 rounded-lg font-semibold hover:bg-gray-100 transition-colors inline-flex items-center"
              >
                <span className="mr-2">访问 GitHub</span>
                <span>→</span>
              </a>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

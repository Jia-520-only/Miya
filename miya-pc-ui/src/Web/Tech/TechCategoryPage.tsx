/**
 * 技术分类详情页面
 * 展示特定技术分类下的所有文章
 */

import { useParams } from 'react-router-dom';
import { useState } from 'react';

interface Article {
  id: number;
  title: string;
  summary: string;
  date: string;
  tags: string[];
  readTime: string;
  githubUrl?: string;
  downloadUrl?: string;
}

const categoryInfo: Record<string, { name: string; icon: string; description: string; color: string }> = {
  linux: {
    name: 'Linux',
    icon: '🐧',
    description: 'Linux 系统管理、Shell 脚本、服务器运维',
    color: 'from-orange-400 to-red-500'
  },
  security: {
    name: '网络安全',
    icon: '🔒',
    description: '渗透测试、漏洞分析、安全防护',
    color: 'from-blue-400 to-indigo-500'
  },
  ai: {
    name: '人工智能',
    icon: '🤖',
    description: '机器学习、深度学习、LLM 应用',
    color: 'from-purple-400 to-pink-500'
  },
  devops: {
    name: 'DevOps',
    icon: '⚙️',
    description: 'CI/CD、Docker、Kubernetes',
    color: 'from-green-400 to-teal-500'
  },
  programming: {
    name: '编程开发',
    icon: '💻',
    description: 'Python、JavaScript、Go 等编程语言',
    color: 'from-cyan-400 to-blue-500'
  },
  database: {
    name: '数据库',
    icon: '🗄️',
    description: 'MySQL、MongoDB、Redis 等',
    color: 'from-yellow-400 to-orange-500'
  }
};

const sampleArticles: Article[] = [
  {
    id: 1,
    title: 'Linux 内核编译与优化实践',
    summary: '详细介绍 Linux 内核编译流程，包括配置选项、编译优化和性能调优技巧。适用于从初学者到高级用户。',
    date: '2026-03-01',
    tags: ['Linux', 'Kernel', 'Performance'],
    readTime: '15 分钟',
    githubUrl: 'https://github.com/example/linux-kernel-tutorial'
  },
  {
    id: 2,
    title: 'Shell 脚本编程进阶指南',
    summary: '深入讲解 Shell 脚本的高级特性，包括函数、数组、正则表达式等，配有实战案例。',
    date: '2026-02-28',
    tags: ['Shell', 'Bash', '脚本'],
    readTime: '12 分钟'
  },
  {
    id: 3,
    title: 'Docker 容器化部署最佳实践',
    summary: '从零开始学习 Docker，包括镜像构建、容器编排和生产环境部署。',
    date: '2026-02-25',
    tags: ['Docker', '容器化', '部署'],
    readTime: '10 分钟',
    downloadUrl: 'https://example.com/docker-guide.zip'
  }
];

export default function TechCategoryPage() {
  const { categoryId } = useParams<{ categoryId: string }>();
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const category = categoryInfo[categoryId || ''] || {
    name: '技术分享',
    icon: '⚡',
    description: '技术学习与分享',
    color: 'from-blue-400 to-purple-500'
  };

  const allTags = Array.from(new Set(sampleArticles.flatMap(article => article.tags)));

  const filteredArticles = selectedTags.length === 0
    ? sampleArticles
    : sampleArticles.filter(article =>
        selectedTags.some(tag => article.tags.includes(tag))
      );

  const toggleTag = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50 dark:from-gray-900 dark:via-slate-900 dark:to-gray-900">
      {/* 页面头部 */}
      <div className={`bg-gradient-to-r ${category.color} text-white py-12`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-4">
            <div className="text-6xl">{category.icon}</div>
            <div>
              <h1 className="text-4xl font-bold mb-2">{category.name}</h1>
              <p className="text-lg text-white/90">{category.description}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* 标签筛选 */}
        <div className="mb-8">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedTags([])}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                selectedTags.length === 0
                  ? 'bg-blue-500 text-white'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              全部
            </button>
            {allTags.map(tag => (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  selectedTags.includes(tag)
                    ? 'bg-blue-500 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>

        {/* 文章列表 */}
        <div className="space-y-6">
          {filteredArticles.map((article) => (
            <article
              key={article.id}
              className="bg-white dark:bg-gray-800 rounded-xl p-8 shadow-lg hover:shadow-xl transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer">
                  {article.title}
                </h3>
                <span className="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap ml-4">
                  {article.readTime}
                </span>
              </div>

              <p className="text-gray-600 dark:text-gray-300 mb-6 text-lg">
                {article.summary}
              </p>

              <div className="flex items-center justify-between">
                <div className="flex flex-wrap gap-2 mb-4 sm:mb-0">
                  {article.tags.map(tag => (
                    <span
                      key={tag}
                      className="px-3 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full text-sm"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                <div className="flex gap-3">
                  {article.githubUrl && (
                    <a
                      href={article.githubUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity flex items-center"
                    >
                      <span className="mr-2">🐙</span>
                      GitHub
                    </a>
                  )}
                  {article.downloadUrl && (
                    <a
                      href={article.downloadUrl}
                      download
                      className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors flex items-center"
                    >
                      <span className="mr-2">📥</span>
                      下载
                    </a>
                  )}
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400">
                发布于 {article.date}
              </div>
            </article>
          ))}

          {filteredArticles.length === 0 && (
            <div className="text-center py-16">
              <div className="text-6xl mb-4">🔍</div>
              <p className="text-xl text-gray-600 dark:text-gray-400">
                没有找到匹配的文章
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

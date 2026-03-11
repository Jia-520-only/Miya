/**
 * 博客列表组件 - 优化版本，参考 Butterfly 主题
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useBlogStore } from '../../store/webStore';
import { blogApi } from '../../services/api';
import BlogCard from './BlogCard';

export default function BlogList() {
  const { posts, total, page, totalPages, loading, setPosts, setLoading } = useBlogStore();
  const [category, setCategory] = useState<string>('');
  const [tag, setTag] = useState<string>('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // 获取博客列表
  const fetchPosts = async () => {
    setLoading(true);
    try {
      const response = await blogApi.getPosts({ page, category, tag });
      setPosts(response.posts, response.total, response.page, response.total_pages);
    } catch (error) {
      console.error('获取博客列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts();
  }, [page, category, tag]);

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            📝 博客
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            共 {total} 篇文章
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* 视图切换 */}
          <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg transition-colors ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400'
                  : 'text-gray-600 dark:text-gray-400'
              }`}
              title="网格视图"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-lg transition-colors ${
                viewMode === 'list'
                  ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400'
                  : 'text-gray-600 dark:text-gray-400'
              }`}
              title="列表视图"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
            </button>
          </div>
          <Link
            to="/blog/new"
            className="px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 transition-all font-medium shadow-md hover:shadow-lg"
          >
            ✨ 新建文章
          </Link>
        </div>
      </div>

      {/* 筛选器 */}
      <div className="flex flex-wrap gap-4">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500 transition-all"
        >
          <option value="">📂 所有分类</option>
          <option value="技术">💻 技术</option>
          <option value="生活">🌸 生活</option>
          <option value="思考">💭 思考</option>
        </select>
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            placeholder="🔍 搜索标签..."
            value={tag}
            onChange={(e) => setTag(e.target.value)}
            className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg bg-white dark:bg-gray-800 dark:border-gray-700 dark:text-white focus:ring-2 focus:ring-blue-500 transition-all"
          />
          <svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* 博客列表 */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="flex flex-col items-center gap-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="text-gray-500 dark:text-gray-400">加载中...</p>
          </div>
        </div>
      ) : posts.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-xl">
          <div className="text-6xl mb-4">📭</div>
          <p className="text-gray-500 dark:text-gray-400 text-lg">
            {category || tag ? '没有找到匹配的文章' : '暂无文章'}
          </p>
          {(category || tag) && (
            <button
              onClick={() => { setCategory(''); setTag(''); }}
              className="mt-4 text-blue-600 hover:text-blue-800 dark:text-blue-400"
            >
              清除筛选
            </button>
          )}
        </div>
      ) : (
        <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : 'space-y-6'}>
          {posts.map((post) => (
            <BlogCard key={post.id} post={post} />
          ))}
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2 mt-8">
          <button
            onClick={() => setPosts(posts, total, Math.max(1, page - 1), totalPages)}
            disabled={page === 1}
            className="px-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 transition-all dark:text-white"
          >
            ← 上一页
          </button>
          
          {/* 页码 */}
          <div className="flex items-center gap-2">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (page <= 3) {
                pageNum = i + 1;
              } else if (page >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = page - 2 + i;
              }

              return (
                <button
                  key={pageNum}
                  onClick={() => setPosts(posts, total, pageNum, totalPages)}
                  className={`w-10 h-10 rounded-lg font-medium transition-all ${
                    page === pageNum
                      ? 'bg-blue-600 text-white'
                      : 'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-white'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setPosts(posts, total, Math.min(totalPages, page + 1), totalPages)}
            disabled={page === totalPages}
            className="px-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700 transition-all dark:text-white"
          >
            下一页 →
          </button>
        </div>
      )}
    </div>
  );
}

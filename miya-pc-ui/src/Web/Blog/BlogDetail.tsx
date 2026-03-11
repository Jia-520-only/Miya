/**
 * 博客详情组件
 */

import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import SimpleMarkdown from '../../utils/SimpleMarkdown';
import { useBlogStore, useAuthStore } from '../../store/webStore';
import { blogApi } from '../../services/api';

export default function BlogDetail() {
  const { slug } = useParams<{ slug: string }>();
  const { currentPost, setCurrentPost, loading, setLoading } = useBlogStore();
  const { user } = useAuthStore();
  const navigate = useNavigate();

  // 获取博客详情
  const fetchPost = async () => {
    if (!slug) return;

    setLoading(true);
    try {
      const post = await blogApi.getPost(slug);
      setCurrentPost(post);
    } catch (error) {
      console.error('获取博客失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPost();
  }, [slug]);

  // 格式化日期
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!currentPost) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        文章不存在
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* 返回按钮 */}
      <Link
        to="/blog"
        className="inline-flex items-center text-blue-600 hover:text-blue-800 dark:text-blue-400 mb-6"
      >
        ← 返回博客列表
      </Link>

      {/* 博客内容 */}
      <article className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-8">
        {/* 标题 */}
        <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
          {currentPost.title}
        </h1>

        {/* 元信息 */}
        <div className="flex flex-wrap gap-4 text-sm text-gray-500 dark:text-gray-400 mb-6 pb-6 border-b border-gray-200 dark:border-gray-700">
          <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full dark:bg-blue-900 dark:text-blue-200">
            {currentPost.category}
          </span>
          <span>作者: {currentPost.author}</span>
          <span>{formatDate(currentPost.created_at)}</span>
          <span>👁 {currentPost.views}</span>
          <span>👍 {currentPost.likes}</span>
        </div>

        {/* 标签 */}
        <div className="flex flex-wrap gap-2 mb-6">
          {currentPost.tags.map((tag) => (
            <span
              key={tag}
              className="text-sm px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-full"
            >
              #{tag}
            </span>
          ))}
        </div>

        {/* Markdown 内容 */}
        <SimpleMarkdown content={currentPost.content} />

        {/* 操作按钮 */}
        {user && user.level >= 2 && (
          <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex gap-4">
            <button
              onClick={() => {
                navigate(`/blog/${currentPost.slug}/edit`);
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              编辑文章
            </button>
            <button
              onClick={async () => {
                if (window.confirm('确定删除这篇文章吗?')) {
                  try {
                    await blogApi.deletePost(currentPost.slug);
                    window.location.href = '/blog';
                  } catch (error) {
                    console.error('删除失败:', error);
                    alert('删除失败');
                  }
                }
              }}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              删除文章
            </button>
          </div>
        )}
      </article>
    </div>
  );
}

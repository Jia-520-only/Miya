/**
 * 博客编辑器组件
 */

import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useBlogStore, useAuthStore } from '../../store/webStore';
import { blogApi } from '../../services/api';

export default function BlogEditor() {
  const { slug } = useParams<{ slug?: string }>();
  const navigate = useNavigate();
  const { currentPost, setCurrentPost } = useBlogStore();
  const { user } = useAuthStore();

  // 解码URL中的slug
  const decodedSlug = slug ? decodeURIComponent(slug) : undefined;

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('技术');
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState('');
  const [published, setPublished] = useState(true);
  const [loading, setLoading] = useState(false);

  const isEditing = !!slug;

  // 加载文章（编辑模式）
  useEffect(() => {
    const loadPost = async () => {
      if (isEditing && decodedSlug) {
        try {
          const post = await blogApi.getPost(decodedSlug);
          setTitle(post.title);
          setContent(post.content);
          setCategory(post.category);
          setTags(post.tags);
          setPublished(post.published);
          setCurrentPost(post);
        } catch (error) {
          console.error('加载文章失败:', error);
          alert('加载文章失败');
          navigate('/blog');
        }
      }
    };

    loadPost();
  }, [isEditing, decodedSlug]);

  // 添加标签
  const handleAddTag = () => {
    if (tagInput && !tags.includes(tagInput)) {
      setTags([...tags, tagInput]);
      setTagInput('');
    }
  };

  // 删除标签
  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter((tag) => tag !== tagToRemove));
  };

  // 保存文章
  const handleSave = async () => {
    if (!title || !content) {
      alert('标题和内容不能为空');
      return;
    }

    setLoading(true);
    try {
      if (isEditing) {
        // 更新文章
        const updatedPost = await blogApi.updatePost(decodedSlug!, {
          title,
          content,
          category,
          tags,
          published,
        });
        setCurrentPost(updatedPost);
      } else {
        // 创建新文章
        const newPost = await blogApi.createPost({
          title,
          content,
          category,
          tags,
          published,
          author: user?.username || 'Unknown',
        });
        navigate(`/blog/${newPost.slug}`);
      }
      alert('保存成功');
    } catch (error) {
      console.error('保存失败:', error);
      alert('保存失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          {isEditing ? '编辑文章' : '新建文章'}
        </h1>
        <button
          onClick={() => navigate('/blog')}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-lg dark:text-white"
        >
          取消
        </button>
      </div>

      {/* 编辑表单 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 space-y-6">
        {/* 标题 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            标题
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            placeholder="输入文章标题"
          />
        </div>

        {/* 分类 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            分类
          </label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          >
            <option value="技术">技术</option>
            <option value="生活">生活</option>
            <option value="思考">思考</option>
          </select>
        </div>

        {/* 标签 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            标签
          </label>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
              placeholder="输入标签后按回车添加"
            />
            <button
              onClick={handleAddTag}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              添加
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full dark:bg-blue-900 dark:text-blue-200"
              >
                {tag}
                <button
                  onClick={() => handleRemoveTag(tag)}
                  className="hover:text-blue-600"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* 内容 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            内容 (Markdown)
          </label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={20}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            placeholder="输入文章内容，支持 Markdown 格式"
          />
        </div>

        {/* 发布状态 */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="published"
            checked={published}
            onChange={(e) => setPublished(e.target.checked)}
            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
          />
          <label htmlFor="published" className="text-gray-700 dark:text-gray-300">
            立即发布
          </label>
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-4">
          <button
            onClick={handleSave}
            disabled={loading}
            className="flex-1 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {loading ? '保存中...' : '保存'}
          </button>
          <button
            onClick={() => navigate('/blog')}
            className="px-6 py-3 bg-gray-200 dark:bg-gray-700 rounded-lg dark:text-white"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

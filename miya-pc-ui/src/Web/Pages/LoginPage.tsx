/**
 * 登录页面
 */

import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../../store/webStore';
import { authApi } from '../../services/api';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, logout, isAuthenticated, user, token } = useAuthStore();

  // 添加调试日志
  console.log('[LoginPage] 当前状态:', { isAuthenticated, user: !!user, hasToken: !!token });
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // 清除本地存储
  const handleClearStorage = () => {
    localStorage.clear();
    sessionStorage.clear();
    logout();
    window.location.reload();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    console.log('[LoginPage] 开始登录, 表单数据:', formData);

    try {
      const response = await authApi.login(formData);
      console.log('[LoginPage] 登录响应:', response);
      if (response.success) {
        console.log('[LoginPage] 登录成功, 用户:', response.user);
        console.log('[LoginPage] 调用 login() 之前, localStorage 内容:', {
          'miya-auth': localStorage.getItem('miya-auth')?.substring(0, 50)
        });

        login(response.user, response.token);

        console.log('[LoginPage] 调用 login() 之后, localStorage 内容:', {
          'miya-auth': localStorage.getItem('miya-auth')?.substring(0, 100)
        });
        console.log('[LoginPage] 当前 store 状态:', {
          isAuthenticated: useAuthStore.getState().isAuthenticated,
          hasUser: !!useAuthStore.getState().user,
          hasToken: !!useAuthStore.getState().token
        });

        console.log('[LoginPage] 正在跳转到仪表板...');
        navigate('/dashboard');
      } else {
        console.log('[LoginPage] 登录失败, 消息:', response.message);
        setError(response.message || '登录失败');
      }
    } catch (error: any) {
      console.error('[LoginPage] 登录异常:', error);
      console.error('[LoginPage] 错误详情:', error.response?.data);
      setError(error.response?.data?.detail || error.response?.data?.message || '登录失败,请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl flex items-center justify-center text-white text-3xl font-bold mx-auto mb-4">
            M
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            欢迎回来
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            登录到弥娅的家园
          </p>
        </div>

        {/* 登录表单 */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                用户名或邮箱
              </label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                placeholder="输入用户名或邮箱"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                密码
              </label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                placeholder="输入密码"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '登录中...' : '登录'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-gray-600 dark:text-gray-400">
              还没有账号?{' '}
              <Link to="/register" className="text-blue-600 hover:text-blue-800 dark:text-blue-400">
                立即注册
              </Link>
            </p>
          </div>

          {/* 默认账号提示 */}
          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>默认管理员账号:</strong><br />
              用户名: admin<br />
              密码: admin123
            </p>
          </div>

          {/* 清除存储按钮 */}
          <button
            type="button"
            onClick={handleClearStorage}
            className="w-full mt-4 px-6 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
          >
            🔄 清除本地存储并刷新
          </button>
        </div>
      </div>
    </div>
  );
}

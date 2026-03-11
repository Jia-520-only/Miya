/**
 * 聊天界面组件 - 柔和青蓝色调
 */

import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '../../store/webStore';
import { chatApi } from '../../services/api';

export default function ChatInterface() {
  const { messages, loading, connected, addMessage, setMessages, setLoading, setConnected } = useChatStore();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 加载历史消息
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const history = await chatApi.getHistory(50);
        setMessages(history);
        setConnected(true);
      } catch (error) {
        console.error('加载历史消息失败:', error);
      }
    };

    loadHistory();
  }, []);

  // 发送消息
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: 'user' as const,
      content: input,
      timestamp: new Date().toISOString(),
    };

    addMessage(userMessage);
    setInput('');
    setLoading(true);

    try {
      const response = await chatApi.sendMessage({ message: input, session_id: 'web' });
      addMessage({
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      console.error('发送消息失败:', error);
      addMessage({
        role: 'assistant',
        content: '抱歉,发送消息时出错了。',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  // 格式化时间
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] card rounded-3xl overflow-hidden">
      {/* 聊天头部 - 柔和设计 */}
      <div className="glass px-6 py-5 border-b border-miya-200/30 dark:border-miya-700/30">
        <div className="flex items-center gap-4">
          {/* 弥娅头像 */}
          <div className="relative">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-miya-400 to-sky-400 flex items-center justify-center text-white text-2xl font-bold shadow-soft animate-pulse-soft">
              M
            </div>
            {/* 在线状态指示器 */}
            <span
              className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full border-2 border-white dark:border-gray-900 ${
                connected ? 'bg-green-400' : 'bg-gray-400'
              }`}
            />
          </div>

          {/* 弥娅名称和状态 */}
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-gradient mb-1">弥娅</h2>
            <div className="flex items-center gap-2">
              <span className="text-sm text-miya-600 dark:text-miya-400">
                {connected ? '🌸 在线' : '💤 离线'}
              </span>
              <div className="h-1 flex-1 bg-gradient-to-r from-miya-300 via-sky-300 to-transparent rounded-full"></div>
            </div>
          </div>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* 空状态 - 柔和的欢迎界面 */}
        {messages.length === 0 && (
          <div className="text-center py-16 animate-slide-up">
            {/* 柔和的装饰元素 */}
            <div className="mb-8">
              <div className="inline-block p-4 rounded-2xl glass">
                <span className="text-6xl">🌸</span>
              </div>
            </div>
            <p className="text-xl mb-3 text-miya-700 dark:text-miya-200 font-semibold">
              你好~ 💙
            </p>
            <p className="text-base text-miya-600 dark:text-miya-400">
              我是弥娅，很高兴与你聊天~ 让我们一起探索这个美好的世界吧 ✨
            </p>
          </div>
        )}

        {/* 消息列表 */}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            } animate-slide-up`}
            style={{ animationDelay: `${index * 0.05}s` }}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-5 py-4 ${
                message.role === 'user'
                  ? 'message-user'
                  : 'message-assistant'
              }`}
            >
              <p className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</p>
              <p
                className={`text-xs mt-2 opacity-70 ${
                  message.role === 'user' ? 'text-white' : 'text-miya-600 dark:text-miya-400'
                }`}
              >
                {formatTime(message.timestamp)}
              </p>
            </div>
          </div>
        ))}

        {/* 加载动画 - 柔和的跳动点 */}
        {loading && (
          <div className="flex justify-start animate-slide-up">
            <div className="message-assistant rounded-2xl px-5 py-4">
              <div className="flex gap-2">
                <span className="loading-dot"></span>
                <span className="loading-dot"></span>
                <span className="loading-dot"></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 - 玻璃态设计 */}
      <div className="p-5 glass border-t border-miya-200/30 dark:border-miya-700/30">
        <div className="flex gap-4">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            rows={3}
            className="input-glass flex-1 px-5 py-4 rounded-2xl resize-none text-miya-900 dark:text-white placeholder:text-miya-400"
            placeholder="在这里输入你的想法... 💭"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="btn-primary px-8 py-4 rounded-2xl text-base font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="loading-dot"></span>
                <span className="loading-dot"></span>
              </span>
            ) : (
              <span className="flex items-center gap-2">
                发送 <span>🚀</span>
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect, useRef } from 'react';
import { chatAPI } from '@shared/api';
import type { Message, EmotionState } from '@shared/types';
import { EMOTION_COLORS, EMOTION_NAMES } from '@shared/constants';

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 从 localStorage 加载聊天记录
  useEffect(() => {
    const saved = localStorage.getItem('miya_chat_history');
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
        console.log('已加载聊天记录:', JSON.parse(saved).length, '条消息');
      } catch (e) {
        console.error('加载聊天记录失败:', e);
      }
    } else {
      console.log('没有找到聊天记录');
    }
  }, []);

  // 保存聊天记录到 localStorage
  useEffect(() => {
    console.log('保存聊天记录:', messages.length, '条消息');
    localStorage.setItem('miya_chat_history', JSON.stringify(messages));
  }, [messages]);

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 发送消息
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatAPI.sendMessage(input);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: response.timestamp,
        emotion: response.emotion,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('发送消息失败:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，我遇到了一些问题，请稍后再试。',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  // 回车发送
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const getDominantEmotion = (emotion: EmotionState) => {
    const entries = Object.entries(emotion);
    return entries.reduce((a, b) => (b[1] as number > a[1] as number ? b : a))[0] as keyof EmotionState;
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 消息列表 */}
      <div className="flex-1 overflow-auto p-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <div className="text-4xl mb-4">👋</div>
            <div className="text-2xl font-bold mb-2">你好，我是弥娅！</div>
            <div>有什么我可以帮你的吗？</div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`mb-4 flex ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[70%] px-4 py-2 rounded-lg ${
                  message.role === 'user'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                <div
                  className={`text-xs mt-1 ${
                    message.role === 'user' ? 'text-indigo-200' : 'text-gray-500'
                  }`}
                >
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
                {message.emotion && message.role === 'assistant' && (
                  <div
                    className="mt-2 inline-block px-2 py-1 rounded text-xs font-bold text-white"
                    style={{
                      backgroundColor:
                        EMOTION_COLORS[getDominantEmotion(message.emotion)] || '#666',
                    }}
                  >
                    {EMOTION_NAMES[getDominantEmotion(message.emotion)]}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="p-4 border-t bg-gray-50">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入消息... (Shift+Enter 换行)"
            rows={3}
            disabled={loading}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className={`px-6 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {loading ? '发送中...' : '发送'}
          </button>
        </div>
      </div>
    </div>
  );
}

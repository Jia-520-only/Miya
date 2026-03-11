import React, { useState } from 'react';
import { chatAPI } from '@shared/api';
import { useStore } from '@store/useStore';

export const QuickChatModal: React.FC = () => {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState('');
  const { showQuickChat, setShowQuickChat, setEmotion } = useStore();

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    setLoading(true);
    try {
      const result = await chatAPI.sendMessage(input);
      setResponse(result.response);
      if (result.emotion) {
        setEmotion(result.emotion);
      }
    } catch (error) {
      console.error('发送消息失败:', error);
      setResponse('抱歉，我遇到了一些问题。');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!showQuickChat) return null;

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={() => setShowQuickChat(false)}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold">快速对话</h3>
          <button
            onClick={() => setShowQuickChat(false)}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        {/* 内容 */}
        <div className="p-4">
          {/* 响应显示 */}
          {response && (
            <div className="mb-4 p-3 bg-gray-50 rounded-lg">
              <p className="text-gray-700">{response}</p>
            </div>
          )}

          {/* 输入框 */}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入你的问题..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm resize-none"
            rows={4}
            disabled={loading}
          />

          {/* 按钮 */}
          <div className="mt-3 flex justify-end space-x-2">
            <button
              onClick={() => setShowQuickChat(false)}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              取消
            </button>
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="px-4 py-2 bg-indigo-600 border border-transparent rounded-md text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? '发送中...' : '发送'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { Live2DModel } from './Live2DModel';
import { EmotionState } from '@shared/types';

interface Live2DAvatarProps {
  emotion: EmotionState;
}

export const Live2DAvatar: React.FC<Live2DAvatarProps> = ({ emotion }) => {
  const [modelPath, setModelPath] = useState<string>(
    // 默认模型路径，用户可以替换
    'https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display/test/assets/shizuku/shizuku.model.json'
  );

  const dominantEmotion = Object.entries(emotion).reduce((a, b) =>
    b[1] > a[1] ? b : a
  )[0] as keyof EmotionState;

  const handleModelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setModelPath(e.target.value);
  };

  return (
    <div className="flex flex-col h-full">
      {/* 模型路径配置 */}
      <div className="p-4 bg-white border-b">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Live2D 模型路径
        </label>
        <input
          type="text"
          value={modelPath}
          onChange={handleModelChange}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          placeholder="输入 Live2D 模型路径"
        />
        <p className="mt-2 text-xs text-gray-500">
          支持本地路径或远程 URL。推荐使用官方或开源模型。
        </p>
      </div>

      {/* Live2D 模型渲染 */}
      <div className="flex-1 bg-gradient-to-b from-gray-50 to-gray-100">
        <Live2DModel
          modelPath={modelPath}
          emotion={dominantEmotion}
          scale={0.2}
        />
      </div>

      {/* 情绪状态显示 */}
      <div className="p-4 bg-white border-t">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">当前情绪</span>
          <span className="text-sm font-semibold text-indigo-600">
            {dominantEmotion}
          </span>
        </div>
        <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${emotion[dominantEmotion] * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
};

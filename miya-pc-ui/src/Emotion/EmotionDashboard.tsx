import React, { useState, useEffect } from 'react';
import { EmotionState } from '@shared/types';
import { emotionAPI } from '@shared/api';
import { EmotionRadar } from './EmotionRadar';
import { EmotionHistoryChart } from './EmotionHistoryChart';
import { EMOTION_COLORS, EMOTION_NAMES } from '@shared/constants';

export const EmotionDashboard: React.FC = () => {
  const [emotion, setEmotion] = useState<EmotionState>({
    happiness: 0.7,
    sadness: 0.1,
    anger: 0.05,
    fear: 0.05,
    surprise: 0.1,
    calm: 0.7,
  });
  const [history, setHistory] = useState<EmotionState[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEmotion = async () => {
      try {
        const current = await emotionAPI.getEmotion();
        setEmotion(current);
        setHistory((prev) => {
          const newHistory = [...prev, current];
          return newHistory.length > 20 ? newHistory.slice(-20) : newHistory;
        });
      } catch (error) {
        console.error('Failed to fetch emotion:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchEmotion();
    const interval = setInterval(fetchEmotion, 5000); // 每5秒更新

    return () => clearInterval(interval);
  }, []);

  const dominantEmotion = Object.entries(emotion).reduce((a, b) =>
    b[1] > a[1] ? b : a
  )[0] as keyof EmotionState;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">加载中...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* 当前情绪概览 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">当前情绪</h3>
        <div className="flex items-center space-x-4">
          <div
            className="w-4 h-4 rounded-full"
            style={{ backgroundColor: EMOTION_COLORS[dominantEmotion] }}
          />
          <span className="text-2xl font-bold">
            {EMOTION_NAMES[dominantEmotion]}
          </span>
          <span className="text-gray-500">
            ({(emotion[dominantEmotion] * 100).toFixed(0)}%)
          </span>
        </div>

        <div className="mt-4 space-y-2">
          {Object.entries(emotion).map(([key, value]) => (
            <div key={key} className="flex items-center space-x-2">
              <div className="w-24 text-sm text-gray-600">{EMOTION_NAMES[key as keyof typeof EMOTION_NAMES]}</div>
              <div className="flex-1 bg-gray-200 rounded-full h-2">
                <div
                  className="h-2 rounded-full transition-all duration-500"
                  style={{
                    width: `${value * 100}%`,
                    backgroundColor: EMOTION_COLORS[key as keyof typeof EMOTION_COLORS],
                  }}
                />
              </div>
              <div className="w-12 text-right text-sm text-gray-600">
                {(value * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 雷达图 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">情绪分布</h3>
        <EmotionRadar emotion={emotion} />
      </div>

      {/* 历史曲线 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">情绪历史趋势</h3>
        <EmotionHistoryChart history={history} />
      </div>
    </div>
  );
};

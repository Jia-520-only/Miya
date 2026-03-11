import React from 'react';
import { EmotionDashboard } from '@Emotion';

export const EmotionPage: React.FC = () => {
  return (
    <div className="h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto py-8 px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">情绪监控</h1>
        <EmotionDashboard />
      </div>
    </div>
  );
};

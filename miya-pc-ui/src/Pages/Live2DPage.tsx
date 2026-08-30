import React from 'react';
import { Live2DAvatar } from '@Live2D';
import { useStore } from '@store/useStore';

export const Live2DPage: React.FC = () => {
  const emotion = useStore((state) => state.emotion);

  return (
    <div className="h-screen bg-gray-50">
      <div className="h-full">
        <Live2DAvatar emotion={emotion || { happiness: 0.7, sadness: 0.1, anger: 0.05, fear: 0.05, surprise: 0.1, calm: 0.7 }} />
      </div>
    </div>
  );
};

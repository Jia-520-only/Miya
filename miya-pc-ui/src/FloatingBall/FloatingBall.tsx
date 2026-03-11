import React, { useState, useRef, useEffect } from 'react';
import { EmotionState } from '@shared/types';

interface FloatingBallProps {
  emotion: EmotionState;
  onQuickChat: () => void;
  onOpenSettings: () => void;
}

export const FloatingBall: React.FC<FloatingBallProps> = ({
  emotion,
  onQuickChat,
  onOpenSettings,
}) => {
  const [position, setPosition] = useState({ x: 100, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const ballRef = useRef<HTMLDivElement>(null);

  const dominantEmotion = Object.entries(emotion).reduce((a, b) =>
    b[1] > a[1] ? b : a
  )[0] as keyof EmotionState;

  const emotionColors: Record<string, string> = {
    happiness: '#22c55e',
    sadness: '#3b82f6',
    anger: '#ef4444',
    fear: '#a855f7',
    surprise: '#eab308',
    calm: '#9ca3af',
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (isExpanded) return;
    setIsDragging(true);
    dragOffset.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    };
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragOffset.current.x,
      y: e.clientY - dragOffset.current.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleClick = () => {
    if (!isDragging) {
      setIsExpanded(!isExpanded);
    }
  };

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const quickActions = [
    { icon: '💬', label: '快速对话', action: onQuickChat },
    { icon: '⚙️', label: '设置', action: onOpenSettings },
  ];

  return (
    <div
      ref={ballRef}
      className="fixed z-50"
      style={{ left: position.x, top: position.y }}
    >
      {/* 快捷操作菜单 */}
      {isExpanded && (
        <div className="absolute bottom-20 left-1/2 transform -translate-x-1/2 space-y-2">
          {quickActions.map((action) => (
            <button
              key={action.label}
              onClick={() => {
                action.action();
                setIsExpanded(false);
              }}
              className="flex items-center space-x-2 bg-white rounded-lg shadow-lg px-4 py-2 hover:bg-gray-50 transition-colors"
            >
              <span className="text-xl">{action.icon}</span>
              <span className="text-sm font-medium">{action.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* 悬浮球主体 */}
      <div
        onClick={handleClick}
        onMouseDown={handleMouseDown}
        className={`w-16 h-16 rounded-full shadow-lg flex items-center justify-center cursor-grab transition-all duration-300 ${
          isExpanded ? 'scale-110' : 'hover:scale-105'
        }`}
        style={{
          backgroundColor: emotionColors[dominantEmotion],
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
      >
        <div className="text-center">
          <div className="text-2xl">🤖</div>
          <div className="text-xs text-white font-bold">
            {isExpanded ? '收起' : '弥娅'}
          </div>
        </div>
      </div>

      {/* 情绪状态指示器 */}
      <div className="absolute -right-8 top-0">
        <div
          className="w-3 h-3 rounded-full border-2 border-white"
          style={{ backgroundColor: emotionColors[dominantEmotion] }}
        />
      </div>
    </div>
  );
};

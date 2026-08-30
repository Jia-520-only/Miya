import React from 'react';
import { EmotionState } from '@shared/types';
import { EMOTION_COLORS } from '@shared/constants';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

interface EmotionRadarProps {
  emotion: EmotionState;
}

export const EmotionRadar: React.FC<EmotionRadarProps> = ({ emotion }) => {
  const data = {
    labels: ['开心', '悲伤', '愤怒', '恐惧', '惊讶', '平静'],
    datasets: [
      {
        label: '当前情绪',
        data: [
          emotion.happiness,
          emotion.sadness,
          emotion.anger,
          emotion.fear,
          emotion.surprise,
          emotion.calm,
        ],
        backgroundColor: 'rgba(99, 102, 241, 0.2)',
        borderColor: 'rgba(99, 102, 241, 1)',
        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgba(99, 102, 241, 1)',
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        beginAtZero: true,
        max: 1,
        ticks: {
          stepSize: 0.2,
          font: {
            size: 10,
          },
        },
        pointLabels: {
          font: {
            size: 12,
            weight: 'bold' as const,
          },
        },
      },
    },
    plugins: {
      legend: {
        display: false,
      },
    },
  };

  return (
    <div className="w-full h-64">
      <Radar data={data} options={options} />
    </div>
  );
};

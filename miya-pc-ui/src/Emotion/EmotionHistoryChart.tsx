import React from 'react';
import { EmotionState } from '@shared/types';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface EmotionHistoryChartProps {
  history: EmotionState[];
}

export const EmotionHistoryChart: React.FC<EmotionHistoryChartProps> = ({ history }) => {
  const labels = history.map((_, index) => {
    const date = new Date();
    date.setMinutes(date.getMinutes() - (history.length - index));
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  });

  const datasets = [
    {
      label: '开心',
      data: history.map((e) => e.happiness),
      borderColor: 'rgb(34, 197, 94)',
      backgroundColor: 'rgba(34, 197, 94, 0.1)',
    },
    {
      label: '悲伤',
      data: history.map((e) => e.sadness),
      borderColor: 'rgb(59, 130, 246)',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
    },
    {
      label: '愤怒',
      data: history.map((e) => e.anger),
      borderColor: 'rgb(239, 68, 68)',
      backgroundColor: 'rgba(239, 68, 68, 0.1)',
    },
    {
      label: '恐惧',
      data: history.map((e) => e.fear),
      borderColor: 'rgb(168, 85, 247)',
      backgroundColor: 'rgba(168, 85, 247, 0.1)',
    },
    {
      label: '惊讶',
      data: history.map((e) => e.surprise),
      borderColor: 'rgb(234, 179, 8)',
      backgroundColor: 'rgba(234, 179, 8, 0.1)',
    },
    {
      label: '平静',
      data: history.map((e) => e.calm),
      borderColor: 'rgb(156, 163, 175)',
      backgroundColor: 'rgba(156, 163, 175, 0.1)',
    },
  ];

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 1,
        ticks: {
          stepSize: 0.2,
        },
      },
    },
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: {
          boxWidth: 12,
          padding: 8,
          font: {
            size: 11,
          },
        },
      },
    },
  };

  return (
    <div className="w-full h-64">
      <Line data={{ labels, datasets }} options={options} />
    </div>
  );
};

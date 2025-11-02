'use client';

import React from 'react';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Legend, Tooltip } from 'chart.js';

ChartJS.register(ArcElement, Legend, Tooltip);

type Props = {
  data: { stage: string; value: number }[];
};

const COLORS = ['#2563eb', '#f97316', '#22c55e', '#eab308', '#9ca3af'];
const stageLabel: Record<string, string> = {
  new: 'Neu',
  learning: 'In Bearbeitung',
  review: 'Review',
  relearn: 'Re-Learning',
  other: 'Sonstige',
};

export default function AnkiStagePie({ data }: Props) {
  if (!data || data.length === 0 || data.every((entry) => entry.value === 0)) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Keine Daten für das Diagramm verfügbar.
      </div>
    );
  }

  const chartData = {
    labels: data.map((entry) => stageLabel[entry.stage] ?? entry.stage),
    datasets: [
      {
        data: data.map((entry) => entry.value),
        backgroundColor: data.map((_, index) => COLORS[index % COLORS.length]),
        borderWidth: 1,
      },
    ],
  };

  return (
    <Pie
      data={chartData}
      options={{
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 14, usePointStyle: true },
          },
        },
      }}
    />
  );
}

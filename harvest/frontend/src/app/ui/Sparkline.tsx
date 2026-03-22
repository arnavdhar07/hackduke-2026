'use client';

import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts';
import type { ZoneScores } from '@/types/api';

interface SparklineProps {
  timeseries: ZoneScores[];
}

export default function Sparkline({ timeseries }: SparklineProps) {
  const data = timeseries.map((d) => ({ ndvi: d.ndvi }));
  const last = data[data.length - 1]?.ndvi ?? 0;
  const color = last < 40 ? '#ef4444' : last < 65 ? '#f59e0b' : last < 80 ? '#84cc16' : '#16a34a';

  return (
    <ResponsiveContainer width="100%" height={32}>
      <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <Tooltip
          contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: 6, fontSize: 10, padding: '2px 6px' }}
          itemStyle={{ color }}
          labelFormatter={() => 'NDVI'}
          formatter={(v: number) => [v, '']}
        />
        <Line type="monotone" dataKey="ndvi" stroke={color} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

'use client';

import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts';
import { ndviColor } from '@/lib/colors';
import type { Zone } from '@/types/api';

interface ZoneSparklineProps {
  zones: Zone[];
}

export default function ZoneSparklines({ zones }: ZoneSparklineProps) {
  if (!zones.length) return null;

  return (
    <div className="shrink-0 border-t border-[#2a3045] px-3 py-2" style={{ backgroundColor: '#0f1117' }}>
      <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1.5">Zone NDVI trends</p>
      <div className="flex gap-2">
        {zones.map((zone) => {
          const latest = zone.latest_scores.ndvi;
          const color  = ndviColor(latest);
          const data   = zone.timeseries.map((d) => ({ ndvi: d.ndvi }));
          return (
            <div key={zone.id} className="flex-1 flex flex-col items-center gap-0.5 rounded-lg px-3 py-2 border border-[#2a3045]" style={{ backgroundColor: '#1a1f2e' }}>
              <ResponsiveContainer width="100%" height={36}>
                <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1f2e', border: '1px solid #2a3045', borderRadius: 4, fontSize: 10, padding: '2px 6px' }}
                    itemStyle={{ color }}
                    labelFormatter={() => zone.label}
                    formatter={(v: number) => [v, 'NDVI']}
                  />
                  <Line
                    type="monotone"
                    dataKey="ndvi"
                    stroke={color}
                    strokeWidth={2}
                    dot={false}
                    style={{ filter: `drop-shadow(0 0 3px ${color})` }}
                  />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                <span className="text-sm font-bold" style={{ color }}>{zone.label}</span>
                <span className="text-sm font-bold ml-1" style={{ color }}>{latest}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

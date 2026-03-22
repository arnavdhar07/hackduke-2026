'use client';

import { ndviColor } from '@/lib/colors';
import type { Zone } from '@/types/api';

interface ZoneSparklineProps {
  zones: Zone[];
}

export default function ZoneSparklines({ zones }: ZoneSparklineProps) {
  if (!zones.length) return null;

  return (
    <div className="shrink-0 border-t border-[#2a3045] px-3 py-2.5" style={{ backgroundColor: '#0f1117' }}>
      <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-2">Zone NDVI</p>
      <div className="flex gap-2">
        {zones.map((zone) => {
          const latest = zone.latest_scores.ndvi;
          const color = ndviColor(latest);
          return (
            <div
              key={zone.id}
              className="flex-1 flex flex-col items-center gap-1 rounded-lg px-2 py-2"
              style={{ backgroundColor: '#1a1f2e' }}
            >
              <span className="text-[10px] text-gray-400 font-medium">{zone.label}</span>
              <span className="text-base font-bold" style={{ color }}>{Math.round(latest)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

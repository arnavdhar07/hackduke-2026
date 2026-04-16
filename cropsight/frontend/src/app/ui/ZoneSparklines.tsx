'use client';

import { ndviColor } from '@/lib/colors';
import type { Zone } from '@/types/api';

interface ZoneSparklineProps {
  zones: Zone[];
  onZoneSelect?: (zone: Zone) => void;
  selectedZoneId?: string;
}

export default function ZoneSparklines({ zones, onZoneSelect, selectedZoneId }: ZoneSparklineProps) {
  if (!zones.length) return null;

  return (
    <div className="shrink-0 border-t border-[#2a3045] px-3 py-2.5" style={{ backgroundColor: '#0f1117' }}>
      <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-2">Zones — click to inspect</p>
      <div className="flex gap-2">
        {zones.map((zone) => {
          const color = ndviColor(zone.latest_scores.ndvi);
          const isSelected = zone.id === selectedZoneId;
          return (
            <button
              key={zone.id}
              onClick={() => onZoneSelect?.(zone)}
              className={`flex-1 flex flex-col items-center gap-1 rounded-lg px-2 py-2 transition-all border ${
                isSelected
                  ? 'border-green-500/60 bg-green-950/30'
                  : 'border-transparent hover:border-gray-600'
              }`}
              style={{ backgroundColor: isSelected ? undefined : '#1a1f2e' }}
            >
              {/* Color dot */}
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              {/* Zone label */}
              <span className="text-[11px] text-gray-300 font-semibold">{zone.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

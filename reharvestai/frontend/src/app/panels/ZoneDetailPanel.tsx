'use client';

import StatCard from '@/app/ui/StatCard';
import NDVIChart from './NDVIChart';
import { ndviColor } from '@/lib/colors';
import type { Zone } from '@/types/api';

interface ZoneDetailPanelProps {
  zone: Zone;
  onClose: () => void;
}

export default function ZoneDetailPanel({ zone, onClose }: ZoneDetailPanelProps) {
  const { ndvi, ndwi, ndre } = zone.latest_scores;

  return (
    <div className="shrink-0 border-t border-gray-800 bg-gray-900 transition-all duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <span
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: ndviColor(ndvi) }}
          />
          <span className="text-sm font-semibold text-white">{zone.label}</span>
          <span className="text-xs text-gray-400">
            {new Date(zone.latest_scores.captured_at).toLocaleDateString('en-US', {
              month: 'short', day: 'numeric',
            })}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-white text-xl leading-none transition-colors"
        >
          ×
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-2 px-4 pb-3">
        <StatCard label="NDVI" value={ndvi} />
        <StatCard label="NDWI" value={ndwi} />
        <StatCard label="NDRE" value={ndre} />
      </div>

      {/* NDVI timeseries chart */}
      <div className="px-4 pb-4">
        <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide">NDVI season</p>
        <NDVIChart timeseries={zone.timeseries} />
      </div>
    </div>
  );
}

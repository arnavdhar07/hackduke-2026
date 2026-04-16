'use client';

import NDVIChart from './NDVIChart';
import { ndviColor } from '@/lib/colors';
import type { Zone } from '@/types/api';

interface ZoneDetailPanelProps {
  zone: Zone;
  onClose: () => void;
}

interface MetricDef {
  key: keyof Zone['latest_scores'];
  label: string;
  fullName: string;
  interpret: (v: number) => string;
  color: (v: number) => string;
}

function barColor(v: number): string {
  if (v >= 75) return '#16a34a';
  if (v >= 55) return '#84cc16';
  if (v >= 35) return '#f59e0b';
  return '#ef4444';
}

const METRICS: MetricDef[] = [
  {
    key: 'ndvi',
    label: 'NDVI',
    fullName: 'Normalized Difference Vegetation Index',
    interpret: (v) =>
      v >= 75 ? 'Dense, healthy canopy — peak biomass or near harvest window.'
      : v >= 55 ? 'Moderate vegetation — crop is growing well, not yet at peak.'
      : v >= 35 ? 'Sparse canopy — early growth, stressed, or soil visible.'
      : 'Very low — bare soil, severe stress, or crop failure.',
    color: barColor,
  },
  {
    key: 'ndwi',
    label: 'NDWI',
    fullName: 'Normalized Difference Water Index',
    interpret: (v) =>
      v >= 65 ? 'Good moisture — adequate hydration, no drought stress.'
      : v >= 45 ? 'Moderate moisture — mild water stress may be developing.'
      : v >= 25 ? 'Low moisture — drought stress likely, consider irrigation.'
      : 'Severe water deficit — crop under significant drought stress.',
    color: barColor,
  },
  {
    key: 'ndre',
    label: 'NDRE',
    fullName: 'Normalized Difference Red Edge',
    interpret: (v) =>
      v >= 65 ? 'High chlorophyll — no early stress signal detected.'
      : v >= 50 ? 'Moderate — minor chlorophyll decline, monitor closely.'
      : v >= 35 ? 'Low — stress onset 2–3 weeks before NDVI will show it.'
      : 'Very low — significant stress already underway.',
    color: barColor,
  },
  {
    key: 'evi',
    label: 'EVI',
    fullName: 'Enhanced Vegetation Index',
    interpret: (v) =>
      v >= 70 ? 'Dense, mature canopy — EVI more reliable than NDVI here.'
      : v >= 50 ? 'Moderate density — crop developing normally.'
      : v >= 30 ? 'Low density — sparse or early-stage canopy.'
      : 'Minimal vegetation signal — possible stress or bare soil.',
    color: barColor,
  },
  {
    key: 'gndvi',
    label: 'GNDVI',
    fullName: 'Green Normalized Difference Vegetation Index',
    interpret: (v) =>
      v >= 70 ? 'Strong late-season chlorophyll — crop still highly active.'
      : v >= 50 ? 'Adequate chlorophyll for the canopy density observed.'
      : v >= 35 ? 'Declining chlorophyll — possible senescence or N deficiency.'
      : 'Low chlorophyll — significant decline in photosynthetic activity.',
    color: barColor,
  },
  {
    key: 'savi',
    label: 'SAVI',
    fullName: 'Soil-Adjusted Vegetation Index',
    interpret: (v) =>
      v >= 65 ? 'Strong vegetation signal even with soil correction applied.'
      : v >= 45 ? 'Moderate — soil influence reduced, reading is reliable.'
      : v >= 25 ? 'Low — sparse cover; soil background dominant.'
      : 'Very sparse — mostly bare soil, very early growth or crop loss.',
    color: barColor,
  },
  {
    key: 'cig',
    label: 'CIg',
    fullName: 'Chlorophyll Index Green',
    interpret: (v) =>
      v >= 60 ? 'High chlorophyll — nitrogen levels appear adequate.'
      : v >= 40 ? 'Moderate — borderline nitrogen, watch for decline.'
      : v >= 20 ? 'Below threshold (40) — nitrogen deficiency likely, consider fertilizing.'
      : 'Critically low — severe chlorophyll/N deficiency.',
    color: (v) => v < 40 ? '#ef4444' : v < 60 ? '#f59e0b' : '#16a34a',
  },
];

export default function ZoneDetailPanel({ zone, onClose }: ZoneDetailPanelProps) {
  const scores = zone.latest_scores;
  const ndvi = scores.ndvi ?? 0;

  return (
    <div className="shrink-0 border-t border-gray-800 bg-gray-900 transition-all duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: ndviColor(ndvi) }} />
          <span className="text-sm font-semibold text-white">{zone.label}</span>
          <span className="text-xs text-gray-400">
            {new Date(scores.captured_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          </span>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none transition-colors">
          ×
        </button>
      </div>

      {/* Metric cards */}
      <div className="px-4 pb-3 flex flex-col gap-2">
        {METRICS.map(({ key, label, fullName, interpret, color }) => {
          const raw = scores[key as keyof typeof scores];
          const v = typeof raw === 'number' ? Math.round(raw) : 0;
          const c = color(v);
          return (
            <div key={key} className="rounded-lg p-3 border border-[#2a3045]" style={{ backgroundColor: '#1a1f2e' }}>
              <div className="flex items-center justify-between mb-1.5">
                <div>
                  <span className="text-xs font-bold text-white">{label}</span>
                  <span className="text-[10px] text-gray-500 ml-1.5">{fullName}</span>
                </div>
                <span className="text-sm font-bold" style={{ color: c }}>{v}</span>
              </div>
              {/* Bar */}
              <div className="h-1 rounded-full bg-gray-700 mb-2">
                <div
                  className="h-1 rounded-full transition-all"
                  style={{ width: `${v}%`, backgroundColor: c }}
                />
              </div>
              {/* Interpretation */}
              <p className="text-[11px] text-gray-400 leading-relaxed">{interpret(v)}</p>
            </div>
          );
        })}
      </div>

      {/* NDVI timeseries chart */}
      <div className="px-4 pb-4">
        <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide">NDVI over season</p>
        <NDVIChart timeseries={zone.timeseries} />
      </div>
    </div>
  );
}

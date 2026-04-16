'use client';

import { useState } from 'react';
import Badge from '@/app/ui/Badge';
import Sparkline from '@/app/ui/Sparkline';
import { Progress, ProgressTrack, ProgressIndicator } from '@/components/ui/progress';
import { patchRecommendation } from '@/lib/api';
import { URGENCY_COLOR } from '@/lib/colors';
import type { Recommendation, Zone, WeatherForecast } from '@/types/api';
import { useQueryClient } from '@tanstack/react-query';
import type { Polygon } from 'geojson';

const ACTION_COLOR: Record<Recommendation['action_type'], string> = {
  harvest: '#ef4444',
  irrigate: '#3b82f6',
  monitor: '#6b7280',
  inspect: '#f59e0b',
  fertilize: '#a855f7',
  spray: '#06b6d4',
  scout: '#84cc16',
  soil_sample: '#78716c',
};

// Left border accent color per urgency
const URGENCY_BORDER: Record<Recommendation['urgency'], string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#3b82f6',
  low: '#6b7280',
};

// Rough polygon area in acres (bounding box approximation)
function polygonAcres(polygon: Polygon): number {
  const coords = polygon.coordinates[0];
  const lngs = coords.map((c) => c[0]);
  const lats = coords.map((c) => c[1]);
  const wKm = (Math.max(...lngs) - Math.min(...lngs)) * 91;
  const hKm = (Math.max(...lats) - Math.min(...lats)) * 111;
  return Math.round(wKm * hKm * 247.105);
}

function hoursUntilRain(forecast: WeatherForecast): number | null {
  const rainDay = forecast.days.find((d) => d.precip_mm > 10);
  if (!rainDay) return null;
  return Math.max(0, Math.round(
    (new Date(rainDay.date + 'T08:00:00').getTime() - Date.now()) / 3_600_000
  ));
}

interface RecommendationCardProps {
  recommendation: Recommendation;
  fieldId: string;
  zone?: Zone;
  forecast?: WeatherForecast;
  cropType?: string;
}

export default function RecommendationCard({
  recommendation: rec,
  fieldId,
  zone,
  forecast,
  cropType,
}: RecommendationCardProps) {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState<string | null>(null);

  async function handleAction(status: 'accepted' | 'deferred' | 'dismissed') {
    setLoading(status);
    queryClient.setQueryData<Recommendation[]>(['recommendations', fieldId], (prev) =>
      prev ? prev.map((r) => (r.id === rec.id ? { ...r, status } : r)) : prev
    );
    try {
      await patchRecommendation(rec.id, status);
    } catch {
      queryClient.invalidateQueries({ queryKey: ['recommendations', fieldId] });
    } finally {
      setLoading(null);
    }
  }

  const showCountdown = (rec.urgency === 'critical' || rec.urgency === 'high') && forecast;
  const hrs = showCountdown ? hoursUntilRain(forecast!) : null;
  const acres = zone ? polygonAcres(zone.polygon) : null;

  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-3 border border-[#2a3045] border-l-[3px]"
      style={{
        backgroundColor: '#1a1f2e',
        borderLeftColor: URGENCY_BORDER[rec.urgency],
      }}
    >

      {/* Header row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${rec.urgency === 'critical' ? 'animate-pulse' : ''}`}
          style={{ backgroundColor: URGENCY_COLOR[rec.urgency] }}
        />
        <span className="text-sm font-bold text-white">{rec.zone_label}</span>
        <Badge label={rec.action_type} color={ACTION_COLOR[rec.action_type]} />
        <span className="ml-auto text-xs text-gray-400 capitalize">{rec.urgency}</span>
      </div>

      {/* Urgency badges row */}
      {(hrs !== null || acres !== null || rec.days_remaining >= 0 || rec.crop_health_rating > 0) && (
        <div className="flex gap-1.5 flex-wrap">
          {hrs !== null && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-blue-900/50 border border-blue-700/50 text-blue-300 whitespace-nowrap">
              ⏱ ~{hrs}h until rain
            </span>
          )}
          {acres !== null && (rec.urgency === 'critical' || rec.urgency === 'high') && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-red-900/40 border border-red-700/40 text-red-300 whitespace-nowrap">
              ~{acres} acres at risk
            </span>
          )}
          {rec.days_remaining >= 0 && (
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md whitespace-nowrap border ${
              rec.days_remaining === 0
                ? 'bg-red-900/50 border-red-700/50 text-red-300'
                : rec.days_remaining <= 3
                ? 'bg-orange-900/50 border-orange-700/50 text-orange-300'
                : 'bg-amber-900/40 border-amber-700/40 text-amber-300'
            }`}>
              {rec.days_remaining === 0 ? '⚠ Past peak' : `⏳ ${rec.days_remaining}d left`}
            </span>
          )}
          {rec.crop_health_rating > 0 && (
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border whitespace-nowrap ${
              rec.crop_health_rating <= 3 ? 'bg-red-900/40 border-red-700/40 text-red-300'
              : rec.crop_health_rating <= 5 ? 'bg-amber-900/40 border-amber-700/40 text-amber-300'
              : rec.crop_health_rating <= 7 ? 'bg-yellow-900/40 border-yellow-700/40 text-yellow-300'
              : 'bg-green-900/40 border-green-700/40 text-green-300'
            }`}>
              Health {rec.crop_health_rating}/10
            </span>
          )}
        </div>
      )}

      {/* Reason */}
      <p className="text-xs text-gray-300 leading-relaxed">{rec.reason}</p>

      {/* AI crop health summary */}
      {rec.crop_health_summary && (
        <p className="text-[11px] text-blue-300/80 leading-relaxed italic border-l-2 border-blue-500/30 pl-2">
          {rec.crop_health_summary}
        </p>
      )}

      {/* Confidence bar */}
      <div className="flex items-center gap-2">
        <Progress value={Math.round(rec.confidence * 100)} className="flex-1 gap-0">
          <ProgressTrack className="h-1 bg-gray-700">
            <ProgressIndicator className="bg-green-500" />
          </ProgressTrack>
        </Progress>
        <span className="text-xs text-gray-400 shrink-0 text-right">{Math.round(rec.confidence * 100)}%</span>
      </div>

      {/* Data signals — all 7 metrics that drove this recommendation */}
      {zone && (
        <div className="rounded-lg px-3 py-2 border border-[#2a3045]" style={{ backgroundColor: '#12161f' }}>
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-2">Satellite signals</p>
          <div className="grid grid-cols-7 gap-1">
            {(
              [
                { k: 'ndvi', l: 'NDVI' },
                { k: 'ndwi', l: 'NDWI' },
                { k: 'ndre', l: 'NDRE' },
                { k: 'evi',  l: 'EVI'  },
                { k: 'gndvi',l: 'GNDVI'},
                { k: 'savi', l: 'SAVI' },
                { k: 'cig',  l: 'CIg'  },
              ] as { k: keyof typeof zone.latest_scores; l: string }[]
            ).map(({ k, l }) => {
              const v = Math.round((zone.latest_scores[k] as number) ?? 0);
              const c = v >= 65 ? '#16a34a' : v >= 45 ? '#84cc16' : v >= 30 ? '#f59e0b' : '#ef4444';
              return (
                <div key={k} className="flex flex-col items-center gap-0.5" title={`${l}: ${v}/100`}>
                  {/* Mini vertical bar */}
                  <div className="w-full h-8 rounded bg-gray-800 relative overflow-hidden">
                    <div
                      className="absolute bottom-0 left-0 right-0 rounded transition-all"
                      style={{ height: `${v}%`, backgroundColor: c, opacity: 0.85 }}
                    />
                  </div>
                  <span className="text-[8px] text-gray-500 leading-none">{l}</span>
                  <span className="text-[8px] font-bold leading-none" style={{ color: c }}>{v}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Yield estimate */}
      {rec.estimated_yield_bushels > 0 && (
        <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
          <span>Est. yield:</span>
          <span className="text-white font-medium">{Math.round(rec.estimated_yield_bushels)} bu</span>
        </div>
      )}

      {/* Divider + Actions */}
      <div className="border-t border-[#2a3045] mt-2 pt-2 flex gap-2">
        <button onClick={() => handleAction('accepted')} disabled={!!loading || rec.status !== 'pending'}
          className="flex-1 text-xs font-medium bg-green-600 hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg py-1.5 transition-colors">
          {loading === 'accepted' ? '…' : 'Accept'}
        </button>
        <button onClick={() => handleAction('deferred')} disabled={!!loading || rec.status !== 'pending'}
          className="flex-1 text-xs font-medium border border-gray-600 hover:border-gray-400 text-gray-300 bg-transparent disabled:opacity-40 disabled:cursor-not-allowed rounded-lg py-1.5 transition-colors">
          {loading === 'deferred' ? '…' : 'Defer'}
        </button>
        <button onClick={() => handleAction('dismissed')} disabled={!!loading || rec.status !== 'pending'}
          className="flex-1 text-xs font-medium text-gray-500 hover:text-gray-300 bg-transparent disabled:opacity-40 disabled:cursor-not-allowed rounded-lg py-1.5 transition-colors">
          {loading === 'dismissed' ? '…' : 'Dismiss'}
        </button>
      </div>
    </div>
  );
}

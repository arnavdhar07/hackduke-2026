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
  onWhyClick: (rec: Recommendation) => void;
  zone?: Zone;
  forecast?: WeatherForecast;
}

export default function RecommendationCard({
  recommendation: rec,
  fieldId,
  onWhyClick,
  zone,
  forecast,
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
      {(hrs !== null || acres !== null) && (
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
        </div>
      )}

      {/* Reason */}
      <p className="text-xs text-gray-300 leading-relaxed">{rec.reason}</p>

      {/* Confidence bar */}
      <div className="flex items-center gap-2">
        <Progress value={Math.round(rec.confidence * 100)} className="flex-1 gap-0">
          <ProgressTrack className="h-1 bg-gray-700">
            <ProgressIndicator className="bg-green-500" />
          </ProgressTrack>
        </Progress>
        <span className="text-xs text-gray-400 shrink-0 text-right">{Math.round(rec.confidence * 100)}%</span>
      </div>

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
        <button onClick={() => onWhyClick(rec)} className="text-xs font-medium text-blue-400 hover:text-blue-300 px-2 transition-colors">
          Why?
        </button>
      </div>
    </div>
  );
}

'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRecommendations } from '@/hooks/useRecommendations';
import { useZones } from '@/hooks/useZones';
import { getWeatherForecast, estimatedRevenueAtRisk } from '@/lib/api';
import RecommendationCard from './RecommendationCard';
import CommunityImpactPanel from './CommunityImpactPanel';
import WeatherStrip from '@/app/ui/WeatherStrip';
import type { Recommendation } from '@/types/api';

const URGENCY_WEIGHT: Record<Recommendation['urgency'], number> = {
  critical: 4, high: 3, medium: 2, low: 1,
};

const URGENCY_OPTIONS: Array<Recommendation['urgency'] | 'all'> = [
  'all', 'critical', 'high', 'medium', 'low',
];

const URGENCY_DOT: Record<Recommendation['urgency'], string> = {
  critical: 'bg-red-400', high: 'bg-orange-400', medium: 'bg-blue-400', low: 'bg-gray-400',
};

interface ActionQueueProps {
  fieldId: string;
  cropType?: string;
  fieldName?: string;
}

export default function ActionQueue({ fieldId, cropType = 'corn', fieldName = '' }: ActionQueueProps) {
  const { recommendations, isLoading, isError, dataUpdatedAt } = useRecommendations(fieldId);
  const { data: zones = [] } = useZones(fieldId);
  const { data: forecast } = useQuery({
    queryKey: ['weather', fieldId],
    queryFn: () => getWeatherForecast(fieldId),
    enabled: !!fieldId,
    staleTime: 5 * 60_000,
  });

  const [urgencyFilter, setUrgencyFilter] = useState<Recommendation['urgency'] | 'all'>('all');
  const [zoneFilter, setZoneFilter] = useState<string>('all');

  const sorted = [...recommendations].sort(
    (a, b) => URGENCY_WEIGHT[b.urgency] - URGENCY_WEIGHT[a.urgency]
  );

  const zoneLabels = Array.from(new Set(recommendations.map((r) => r.zone_label))).sort();

  const filtered = sorted.filter((r) => {
    if (urgencyFilter !== 'all' && r.urgency !== urgencyFilter) return false;
    if (zoneFilter !== 'all' && r.zone_label !== zoneFilter) return false;
    return true;
  });

  const active = filtered.filter((r) => r.status === 'pending');
  const actioned = filtered.filter((r) => r.status !== 'pending');

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    : null;

  // Total revenue at risk across all pending recommendations
  const totalRevenueAtRisk = active.reduce((sum, rec) => {
    return sum + estimatedRevenueAtRisk(rec.estimated_yield_bushels ?? 0, cropType ?? '', rec.confidence);
  }, 0);

  // Pipeline is still running: fetched at least once but got zero results
  const isPipelineRunning = !isLoading && !isError && recommendations.length === 0;

  if (isLoading || isPipelineRunning) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 px-6 py-14 text-center">
        {/* Animated satellite orbit */}
        <div className="relative w-14 h-14">
          <div className="absolute inset-0 rounded-full border border-green-900/40" />
          <div
            className="absolute inset-0 rounded-full border-t-2 border-green-500 animate-spin"
            style={{ animationDuration: '1.4s' }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.2" className="w-5 h-5 text-green-400">
              <circle cx="10" cy="10" r="3" fill="currentColor" opacity=".6"/>
              <path d="M10 2a8 8 0 0 1 8 8" strokeLinecap="round" opacity=".4"/>
              <path d="M10 18a8 8 0 0 1-8-8" strokeLinecap="round" opacity=".4"/>
            </svg>
          </div>
        </div>
        <div>
          <p className="text-sm font-semibold text-white mb-1">Analysing your field</p>
          <p className="text-xs text-gray-500 leading-relaxed">
            Fetching satellite imagery and<br />running the AI agent…
          </p>
        </div>
        {/* Animated steps */}
        <div className="w-full max-w-[200px] flex flex-col gap-1.5 mt-1">
          {['Fetching satellite data', 'Computing indices', 'Running AI agent'].map((step, i) => (
            <div key={step} className="flex items-center gap-2">
              <div
                className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse shrink-0"
                style={{ animationDelay: `${i * 0.4}s` }}
              />
              <span className="text-[11px] text-gray-500">{step}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return <div className="p-8 text-center"><p className="text-xs text-red-400">Failed to load recommendations.</p></div>;
  }

  return (
    <>
      {/* Community Impact — top of scroll area, collapsible */}
      <CommunityImpactPanel cropType={cropType} fieldName={fieldName} />

      {/* Weather strip */}
      {forecast && <WeatherStrip days={forecast.days} />}

      {/* Revenue at risk summary */}
      {totalRevenueAtRisk > 0 && (
        <div className="mx-4 mt-3 px-4 py-3 rounded-xl border border-red-500/20 bg-red-950/20 flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-white">Revenue at risk</p>
            <p className="text-[10px] text-gray-400 mt-0.5">Across {active.length} pending actions</p>
          </div>
          <span className="text-xl font-bold text-red-400">${totalRevenueAtRisk.toLocaleString()}</span>
        </div>
      )}

      {/* Filter bar */}
      <div className="px-4 pt-3 pb-2 border-b border-[#2a3045] flex flex-col gap-2">
        <div className="flex gap-1.5 flex-wrap">
          {URGENCY_OPTIONS.map((u) => (
            <button
              key={u}
              onClick={() => setUrgencyFilter(u)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                urgencyFilter === u
                  ? 'bg-white text-gray-950 border-white'
                  : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
              }`}
            >
              {u !== 'all' && (
                <span
                  className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    u === 'critical' ? 'animate-pulse ' : ''
                  }${URGENCY_DOT[u as Recommendation['urgency']]}`}
                />
              )}
              {u.charAt(0).toUpperCase() + u.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex items-center justify-between gap-2">
          <select
            value={zoneFilter}
            onChange={(e) => setZoneFilter(e.target.value)}
            className="text-[11px] border border-[#2a3045] text-gray-300 rounded-md px-2 py-1 focus:outline-none"
            style={{ backgroundColor: '#1a1f2e' }}
          >
            <option value="all">All zones</option>
            {zoneLabels.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
          {lastUpdated && <span className="text-[10px] text-gray-600 shrink-0">Updated {lastUpdated}</span>}
        </div>
      </div>

      {/* Recommendation cards */}
      <div className="p-4 flex flex-col gap-3">
        {active.length === 0 && actioned.length === 0 && (
          <p className="text-xs text-gray-500 text-center py-8">No recommendations match this filter.</p>
        )}
        {active.map((rec) => (
          <RecommendationCard
            key={rec.id}
            recommendation={rec}
            fieldId={fieldId}
            zone={zones.find((z) => z.id === rec.zone_id)}
            forecast={forecast}
            cropType={cropType}
          />
        ))}
        {actioned.length > 0 && (
          <>
            <p className="text-[10px] text-gray-600 uppercase tracking-widest mt-2 px-1">Actioned</p>
            {actioned.map((rec) => (
              <div key={rec.id} className="opacity-40">
                <RecommendationCard
                  recommendation={rec}
                  fieldId={fieldId}
                  zone={zones.find((z) => z.id === rec.zone_id)}
                  forecast={forecast}
                  cropType={cropType}
                />
              </div>
            ))}
          </>
        )}
      </div>
    </>
  );
}

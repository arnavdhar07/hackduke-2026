'use client';

import { useState } from 'react';
import Badge from '@/app/ui/Badge';
import { patchRecommendation } from '@/lib/api';
import { URGENCY_COLOR } from '@/lib/colors';
import type { Recommendation } from '@/types/api';
import { useQueryClient } from '@tanstack/react-query';

const ACTION_COLOR: Record<Recommendation['action_type'], string> = {
  harvest: '#ef4444',
  irrigate: '#3b82f6',
  monitor: '#6b7280',
  inspect: '#f59e0b',
};

interface RecommendationCardProps {
  recommendation: Recommendation;
  fieldId: string;
}

export default function RecommendationCard({ recommendation: rec, fieldId }: RecommendationCardProps) {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState<string | null>(null);

  async function handleAction(status: 'accepted' | 'deferred' | 'dismissed') {
    setLoading(status);
    // Optimistic update
    queryClient.setQueryData<Recommendation[]>(['recommendations', fieldId], (prev) =>
      prev ? prev.map((r) => (r.id === rec.id ? { ...r, status } : r)) : prev
    );
    try {
      await patchRecommendation(rec.id, status);
    } catch {
      // Revert on failure
      queryClient.invalidateQueries({ queryKey: ['recommendations', fieldId] });
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className={`bg-gray-800 rounded-xl p-4 flex flex-col gap-3 ${rec.urgency === 'critical' ? 'ring-1 ring-red-500/60' : ''}`}>
      {/* Header row */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Urgency dot */}
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${rec.urgency === 'critical' ? 'animate-pulse' : ''}`}
          style={{ backgroundColor: URGENCY_COLOR[rec.urgency] }}
        />
        <span className="text-sm font-semibold text-white">{rec.zone_label}</span>
        <Badge label={rec.action_type} color={ACTION_COLOR[rec.action_type]} />
        <span className="ml-auto text-xs text-gray-400 capitalize">{rec.urgency}</span>
      </div>

      {/* Reason */}
      <p className="text-xs text-gray-300 leading-relaxed">{rec.reason}</p>

      {/* Confidence */}
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-gray-700 rounded-full h-1">
          <div
            className="h-1 rounded-full bg-green-500"
            style={{ width: `${Math.round(rec.confidence * 100)}%` }}
          />
        </div>
        <span className="text-xs text-gray-400">{Math.round(rec.confidence * 100)}% confidence</span>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => handleAction('accepted')}
          disabled={!!loading || rec.status !== 'pending'}
          className="flex-1 text-xs font-medium bg-green-700 hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg py-1.5 transition-colors"
        >
          {loading === 'accepted' ? '…' : 'Accept'}
        </button>
        <button
          onClick={() => handleAction('deferred')}
          disabled={!!loading || rec.status !== 'pending'}
          className="flex-1 text-xs font-medium bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg py-1.5 transition-colors"
        >
          {loading === 'deferred' ? '…' : 'Defer'}
        </button>
        <button
          onClick={() => handleAction('dismissed')}
          disabled={!!loading || rec.status !== 'pending'}
          className="flex-1 text-xs font-medium bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg py-1.5 transition-colors"
        >
          {loading === 'dismissed' ? '…' : 'Dismiss'}
        </button>
      </div>
    </div>
  );
}

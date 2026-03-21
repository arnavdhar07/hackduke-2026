'use client';

import { useState } from 'react';
import { useRecommendations } from '@/hooks/useRecommendations';
import RecommendationCard from './RecommendationCard';
import type { Recommendation } from '@/types/api';

const URGENCY_WEIGHT: Record<Recommendation['urgency'], number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

interface ActionQueueProps {
  fieldId: string;
}

export default function ActionQueue({ fieldId }: ActionQueueProps) {
  const { recommendations, isLoading, isError } = useRecommendations(fieldId);

  const sorted = [...recommendations].sort(
    (a, b) => URGENCY_WEIGHT[b.urgency] - URGENCY_WEIGHT[a.urgency]
  );

  const active = sorted.filter((r) => r.status === 'pending');
  const actioned = sorted.filter((r) => r.status !== 'pending');

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-xs text-gray-500">Loading recommendations…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-xs text-red-400">Failed to load recommendations.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-4 flex flex-col gap-3">
        {active.length === 0 && actioned.length === 0 && (
          <p className="text-xs text-gray-500 text-center py-8">No recommendations yet.</p>
        )}

        {active.map((rec) => (
          <RecommendationCard
            key={rec.id}
            recommendation={rec}
            fieldId={fieldId}
          />
        ))}

        {actioned.length > 0 && (
          <>
            <p className="text-xs text-gray-500 uppercase tracking-wide mt-2">Actioned</p>
            {actioned.map((rec) => (
              <div key={rec.id} className="opacity-40">
                <RecommendationCard
                  recommendation={rec}
                  fieldId={fieldId}
                />
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

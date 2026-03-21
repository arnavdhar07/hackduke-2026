import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState, useCallback } from 'react';
import { getRecommendations } from '@/lib/api';
import type { Recommendation } from '@/types/api';

export function useRecommendations(fieldId: string) {
  const [criticalToast, setCriticalToast] = useState<string | null>(null);
  const seenIds = useRef<Set<string>>(new Set());
  const initialised = useRef(false);

  const query = useQuery({
    queryKey: ['recommendations', fieldId],
    queryFn: async () => {
      const data = await getRecommendations(fieldId);

      // Run detection inside queryFn so it fires exactly once per fetch,
      // regardless of React's render cycle or effect timing.
      if (!initialised.current) {
        // On first load, mark all existing IDs as seen without toasting.
        data.forEach((r) => seenIds.current.add(r.id));
        initialised.current = true;
      } else {
        // On subsequent fetches, toast any new critical recs.
        const newCritical = data.find(
          (r) => r.urgency === 'critical' && r.status === 'pending' && !seenIds.current.has(r.id)
        );
        data.forEach((r) => seenIds.current.add(r.id));
        if (newCritical) {
          setCriticalToast(newCritical.reason);
        }
      }

      return data;
    },
    enabled: !!fieldId,
    refetchInterval: 60_000,
  });

  const clearToast = useCallback(() => setCriticalToast(null), []);

  return {
    ...query,
    recommendations: query.data ?? [],
    criticalToast,
    clearToast,
  };
}

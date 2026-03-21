import { useQuery } from '@tanstack/react-query';
import { getZones } from '@/lib/api';

export function useZones(fieldId: string) {
  return useQuery({
    queryKey: ['zones', fieldId],
    queryFn: () => getZones(fieldId),
    enabled: !!fieldId,
    // Poll every 3s until zones appear (pipeline seeding takes ~2s), then stop.
    refetchInterval: (query) =>
      (query.state.data?.length ?? 0) === 0 ? 3_000 : false,
  });
}

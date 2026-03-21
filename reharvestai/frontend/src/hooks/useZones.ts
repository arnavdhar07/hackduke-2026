import { useQuery } from '@tanstack/react-query';
import { getZones } from '@/lib/api';

export function useZones(fieldId: string) {
  return useQuery({
    queryKey: ['zones', fieldId],
    queryFn: () => getZones(fieldId),
    enabled: !!fieldId,
  });
}

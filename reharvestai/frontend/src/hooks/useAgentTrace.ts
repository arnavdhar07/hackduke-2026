import { useQuery } from '@tanstack/react-query';
import { getAgentTrace } from '@/lib/api';

export function useAgentTrace(fieldId: string) {
  const query = useQuery({
    queryKey: ['agentTrace', fieldId],
    queryFn: () => getAgentTrace(fieldId),
    enabled: false,
  });

  return {
    ...query,
    fetch: query.refetch,
  };
}

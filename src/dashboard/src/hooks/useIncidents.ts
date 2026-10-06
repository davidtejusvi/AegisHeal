import { useQuery } from '@tanstack/react-query';
import { remediationClient } from '../api/client';
import type { IncidentsResponse } from '../api/types';

export function useIncidents(limit = 50) {
  return useQuery<IncidentsResponse, Error>({
    queryKey: ['incidents', limit],
    queryFn: async () => {
      const { data } = await remediationClient.get<IncidentsResponse>(`/incidents?limit=${limit}`);
      return data;
    },
    refetchInterval: 10000,
    retry: 2,
  });
}

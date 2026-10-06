import { useQuery } from '@tanstack/react-query';
import { remediationClient } from '../api/client';
import type { StatsResponse } from '../api/types';

export function useStats() {
  return useQuery<StatsResponse, Error>({
    queryKey: ['stats'],
    queryFn: async () => {
      const { data } = await remediationClient.get<StatsResponse>('/stats');
      return data;
    },
    refetchInterval: 15000,
    retry: 2,
  });
}

import { useQuery } from '@tanstack/react-query';
import { anomalyClient } from '../api/client';
import type { AnomaliesResponse } from '../api/types';

export function useAnomalies(limit = 50) {
  return useQuery<AnomaliesResponse, Error>({
    queryKey: ['anomalies', limit],
    queryFn: async () => {
      const { data } = await anomalyClient.get<AnomaliesResponse>(`/anomalies?limit=${limit}`);
      return data;
    },
    refetchInterval: 10000,
    retry: 2,
  });
}

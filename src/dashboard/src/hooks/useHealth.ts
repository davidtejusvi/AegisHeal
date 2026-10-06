import { useQuery } from '@tanstack/react-query';
import { anomalyClient, remediationClient } from '../api/client';
import type { HealthResponse } from '../api/types';

export function useAnomalyHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: ['health', 'anomaly'],
    queryFn: async () => {
      const { data } = await anomalyClient.get<HealthResponse>('/health');
      return data;
    },
    refetchInterval: 15000,
    retry: 2,
  });
}

export function useRemediationHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: ['health', 'remediation'],
    queryFn: async () => {
      const { data } = await remediationClient.get<HealthResponse>('/health');
      return data;
    },
    refetchInterval: 15000,
    retry: 2,
  });
}

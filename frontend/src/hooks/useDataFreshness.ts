/**
 * Hook for managing data freshness and staleness detection.
 */
import { useState, useEffect, useCallback } from 'react';

export interface StalenessInfo {
  exists: boolean;
  is_stale: boolean;
  last_analyzed?: string;
  age_hours?: number;
  threshold_hours?: number;
  reason: string;
}

export interface RefreshStatus {
  isRefreshing: boolean;
  lastRefresh?: Date;
  error?: string;
}

export function useDataFreshness(repoId: string, branchName: string) {
  const [stalenessInfo, setStalenessInfo] = useState<StalenessInfo | null>(null);
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus>({
    isRefreshing: false,
  });
  const [loading, setLoading] = useState(false);

  const checkStaleness = useCallback(async () => {
    if (!repoId || !branchName) return;

    setLoading(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/refresh/staleness/${repoId}/${branchName}`
      );

      if (!response.ok) {
        throw new Error('Failed to check staleness');
      }

      const data = await response.json();
      setStalenessInfo(data);
    } catch (error) {
      console.error('Error checking staleness:', error);
      setStalenessInfo({
        exists: false,
        is_stale: true,
        reason: 'Failed to check staleness',
      });
    } finally {
      setLoading(false);
    }
  }, [repoId, branchName]);

  const markForRefresh = useCallback(async () => {
    if (!repoId || !branchName) return;

    setRefreshStatus({ isRefreshing: true });
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/refresh/mark/${repoId}/${branchName}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to mark for refresh');
      }

      setRefreshStatus({
        isRefreshing: false,
        lastRefresh: new Date(),
      });

      // Re-check staleness after marking for refresh
      await checkStaleness();
    } catch (error) {
      console.error('Error marking for refresh:', error);
      setRefreshStatus({
        isRefreshing: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [repoId, branchName, checkStaleness]);

  const triggerAnalysis = useCallback(async () => {
    if (!repoId || !branchName) return;

    setRefreshStatus({ isRefreshing: true });
    try {
      // Trigger async analysis
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/analyze-async`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            repo_id: repoId,
            branch: branchName,
            priority: 1,
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to trigger analysis');
      }

      const data = await response.json();

      setRefreshStatus({
        isRefreshing: false,
        lastRefresh: new Date(),
      });

      // Re-check staleness after triggering analysis
      await checkStaleness();

      return data.task_id;
    } catch (error) {
      console.error('Error triggering analysis:', error);
      setRefreshStatus({
        isRefreshing: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
      return null;
    }
  }, [repoId, branchName, checkStaleness]);

  // Check staleness on mount and when dependencies change
  useEffect(() => {
    checkStaleness();
  }, [checkStaleness]);

  // Auto-refresh staleness check every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      checkStaleness();
    }, 5 * 60 * 1000); // 5 minutes

    return () => clearInterval(interval);
  }, [checkStaleness]);

  return {
    stalenessInfo,
    refreshStatus,
    loading,
    checkStaleness,
    markForRefresh,
    triggerAnalysis,
  };
}

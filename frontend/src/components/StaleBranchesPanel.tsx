/**
 * Component to display and manage stale branches.
 */
import React, { useState, useEffect } from 'react';

interface StaleBranchesPanelProps {
  repoId: string;
  onRefreshBranch?: (branchName: string) => void;
}

export function StaleBranchesPanel({ repoId, onRefreshBranch }: StaleBranchesPanelProps) {
  const [staleBranches, setStaleBranches] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const fetchStaleBranches = async () => {
    if (!repoId) return;

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/refresh/stale-branches/${repoId}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch stale branches');
      }

      const data = await response.json();
      setStaleBranches(data.stale_branches || []);
    } catch (err) {
      console.error('Error fetching stale branches:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshBranch = async (branchName: string) => {
    setRefreshing((prev) => new Set(prev).add(branchName));
    
    try {
      // Mark for refresh
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/refresh/mark/${repoId}/${branchName}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error('Failed to mark branch for refresh');
      }

      // Trigger analysis
      await fetch(
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

      // Notify parent component
      if (onRefreshBranch) {
        onRefreshBranch(branchName);
      }

      // Refresh the list
      await fetchStaleBranches();
    } catch (err) {
      console.error('Error refreshing branch:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setRefreshing((prev) => {
        const next = new Set(prev);
        next.delete(branchName);
        return next;
      });
    }
  };

  const handleRefreshAll = async () => {
    for (const branch of staleBranches) {
      await handleRefreshBranch(branch);
    }
  };

  useEffect(() => {
    fetchStaleBranches();
  }, [repoId]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      fetchStaleBranches();
    }, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [repoId]);

  if (loading && staleBranches.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <div className="flex items-center gap-2 text-gray-500">
          <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-blue-500 rounded-full" />
          <span>Checking for stale branches...</span>
        </div>
      </div>
    );
  }

  if (staleBranches.length === 0) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-green-600">
            <span className="text-lg">✓</span>
            <span className="font-semibold">All branches are up to date</span>
          </div>
          <button
            onClick={fetchStaleBranches}
            disabled={loading}
            className="text-sm px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50"
          >
            {loading ? '⟳' : '↻'} Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg text-yellow-600">⚠️</span>
          <h3 className="font-semibold text-gray-900">
            Stale Branches ({staleBranches.length})
          </h3>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchStaleBranches}
            disabled={loading}
            className="text-sm px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50"
            title="Refresh list"
          >
            {loading ? '⟳' : '↻'}
          </button>
          <button
            onClick={handleRefreshAll}
            disabled={refreshing.size > 0}
            className="text-sm px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
            title="Refresh all stale branches"
          >
            Refresh All
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          Error: {error}
        </div>
      )}

      <div className="space-y-2">
        {staleBranches.map((branch) => (
          <div
            key={branch}
            className="flex items-center justify-between p-3 bg-gray-50 rounded border border-gray-200"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono text-gray-700">{branch}</span>
              <span className="text-xs text-gray-500">needs refresh</span>
            </div>
            <button
              onClick={() => handleRefreshBranch(branch)}
              disabled={refreshing.has(branch)}
              className="text-sm px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {refreshing.has(branch) ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        ))}
      </div>

      <div className="mt-4 text-xs text-gray-500">
        <p>
          Branches are considered stale if they haven't been analyzed in the last 24 hours.
          Refreshing will trigger a new analysis.
        </p>
      </div>
    </div>
  );
}

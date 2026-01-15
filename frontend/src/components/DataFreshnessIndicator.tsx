/**
 * Component to display data freshness indicators and refresh controls.
 */
import React from 'react';
import { useDataFreshness } from '@/hooks/useDataFreshness';

interface DataFreshnessIndicatorProps {
  repoId: string;
  branchName: string;
  compact?: boolean;
}

export function DataFreshnessIndicator({
  repoId,
  branchName,
  compact = false,
}: DataFreshnessIndicatorProps) {
  const {
    stalenessInfo,
    refreshStatus,
    loading,
    checkStaleness,
    triggerAnalysis,
  } = useDataFreshness(repoId, branchName);

  if (loading && !stalenessInfo) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-blue-500 rounded-full" />
        <span>Checking freshness...</span>
      </div>
    );
  }

  if (!stalenessInfo) {
    return null;
  }

  const getStatusColor = () => {
    if (!stalenessInfo.exists) return 'text-gray-500';
    if (stalenessInfo.is_stale) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getStatusIcon = () => {
    if (!stalenessInfo.exists) return '❓';
    if (stalenessInfo.is_stale) return '⚠️';
    return '✓';
  };

  const getStatusText = () => {
    if (!stalenessInfo.exists) return 'No data';
    if (stalenessInfo.is_stale) return 'Stale data';
    return 'Fresh data';
  };

  const formatAge = () => {
    if (!stalenessInfo.age_hours) return '';
    
    if (stalenessInfo.age_hours < 1) {
      return `${Math.round(stalenessInfo.age_hours * 60)} minutes ago`;
    } else if (stalenessInfo.age_hours < 24) {
      return `${Math.round(stalenessInfo.age_hours)} hours ago`;
    } else {
      return `${Math.round(stalenessInfo.age_hours / 24)} days ago`;
    }
  };

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className={`text-sm ${getStatusColor()}`}>
          {getStatusIcon()} {getStatusText()}
        </span>
        {stalenessInfo.is_stale && (
          <button
            onClick={triggerAnalysis}
            disabled={refreshStatus.isRefreshing}
            className="text-xs px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Refresh data"
          >
            {refreshStatus.isRefreshing ? '⟳' : '↻'}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-lg ${getStatusColor()}`}>{getStatusIcon()}</span>
            <h3 className={`font-semibold ${getStatusColor()}`}>{getStatusText()}</h3>
          </div>
          
          <div className="text-sm text-gray-600 space-y-1">
            <p>{stalenessInfo.reason}</p>
            
            {stalenessInfo.last_analyzed && (
              <p className="text-xs text-gray-500">
                Last analyzed: {formatAge()}
              </p>
            )}
            
            {stalenessInfo.is_stale && stalenessInfo.threshold_hours && (
              <p className="text-xs text-gray-500">
                Data is considered stale after {stalenessInfo.threshold_hours} hours
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={checkStaleness}
            disabled={loading}
            className="text-sm px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Check freshness"
          >
            {loading ? '⟳' : '↻'} Check
          </button>
          
          {stalenessInfo.is_stale && (
            <button
              onClick={triggerAnalysis}
              disabled={refreshStatus.isRefreshing}
              className="text-sm px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Refresh data"
            >
              {refreshStatus.isRefreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          )}
        </div>
      </div>

      {refreshStatus.error && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          Error: {refreshStatus.error}
        </div>
      )}

      {refreshStatus.lastRefresh && (
        <div className="mt-3 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-700">
          Refresh triggered at {refreshStatus.lastRefresh.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}

'use client'

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, GitBranch, TrendingUp, TrendingDown, Minus, Loader2, AlertTriangle, Brain, BarChart3, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { HistoricalTrendChart } from './HistoricalTrendChart'

interface BranchComparisonModalProps {
    isOpen: boolean
    onClose: () => void
    repoId: string
    baseBranch: string
    compareBranch: string
    onExplainComparison?: (baseBranch: string, compareBranch: string) => void
}

interface ScoreDifference {
    overall_score_diff: number
    category_diffs: {
        [key: string]: number
    }
}

interface QualityChange {
    category: string
    change_type: 'IMPROVEMENT' | 'REGRESSION' | 'NO_CHANGE'
    magnitude: number
    description: string
    affected_files: string[]
}

interface BranchComparison {
    base_branch: string
    compare_branch: string
    score_diff: ScoreDifference
    quality_changes: QualityChange[]
    recommendations: string[]
}

export const BranchComparisonModal: React.FC<BranchComparisonModalProps> = ({
    isOpen,
    onClose,
    repoId,
    baseBranch,
    compareBranch,
    onExplainComparison
}) => {
    const [comparison, setComparison] = useState<BranchComparison | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string>('')
    const [activeTab, setActiveTab] = useState<'comparison' | 'trends'>('comparison')

    useEffect(() => {
        if (isOpen && baseBranch && compareBranch) {
            fetchComparison()
        }
    }, [isOpen, baseBranch, compareBranch, repoId]) // eslint-disable-line react-hooks/exhaustive-deps

    const fetchComparison = async () => {
        setLoading(true)
        setError('')
        
        try {
            const response = await api.get(`/compare-branches/${repoId}`, {
                params: {
                    base_branch: baseBranch,
                    compare_branch: compareBranch
                }
            })
            setComparison(response.data.comparison)
        } catch (err: any) {
            console.error('Failed to fetch branch comparison:', err)
            setError(err.response?.data?.detail || 'Failed to compare branches')
        } finally {
            setLoading(false)
        }
    }

    const getChangeIcon = (changeType: string) => {
        switch (changeType) {
            case 'IMPROVEMENT':
                return <TrendingUp className="h-4 w-4 text-green-400" />
            case 'REGRESSION':
                return <TrendingDown className="h-4 w-4 text-red-400" />
            default:
                return <Minus className="h-4 w-4 text-gray-400" />
        }
    }

    const getChangeColor = (changeType: string) => {
        switch (changeType) {
            case 'IMPROVEMENT':
                return 'text-green-400 bg-green-500/10 border-green-500/20'
            case 'REGRESSION':
                return 'text-red-400 bg-red-500/10 border-red-500/20'
            default:
                return 'text-gray-400 bg-gray-500/10 border-gray-500/20'
        }
    }

    const formatScoreDiff = (diff: number) => {
        const sign = diff > 0 ? '+' : ''
        return `${sign}${diff.toFixed(1)}`
    }

    if (!isOpen) return null

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                onClick={onClose}
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 20 }}
                    transition={{ duration: 0.2 }}
                    className="bg-black/90 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden"
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between p-6 border-b border-white/10">
                        <div className="flex items-center gap-3">
                            <GitBranch className="h-6 w-6 text-primary" />
                            <div>
                                <h2 className="text-xl font-semibold">Branch Comparison</h2>
                                <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                                    <span className="font-mono bg-white/5 px-2 py-1 rounded border border-white/10">
                                        {baseBranch}
                                    </span>
                                    <span>vs</span>
                                    <span className="font-mono bg-white/5 px-2 py-1 rounded border border-white/10">
                                        {compareBranch}
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            {onExplainComparison && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => onExplainComparison(baseBranch, compareBranch)}
                                    className="gap-2"
                                >
                                    <Brain className="h-4 w-4" />
                                    Explain
                                </Button>
                            )}
                            <Button variant="ghost" size="icon" onClick={onClose}>
                                <X className="h-5 w-5" />
                            </Button>
                        </div>
                    </div>

                    {/* Tab Navigation */}
                    <div className="flex border-b border-white/10">
                        <button
                            onClick={() => setActiveTab('comparison')}
                            className={cn(
                                "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                                activeTab === 'comparison'
                                    ? "border-primary text-primary"
                                    : "border-transparent text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <div className="flex items-center gap-2">
                                <GitBranch className="h-4 w-4" />
                                Comparison
                            </div>
                        </button>
                        <button
                            onClick={() => setActiveTab('trends')}
                            className={cn(
                                "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                                activeTab === 'trends'
                                    ? "border-primary text-primary"
                                    : "border-transparent text-muted-foreground hover:text-foreground"
                            )}
                        >
                            <div className="flex items-center gap-2">
                                <BarChart3 className="h-4 w-4" />
                                Historical Trends
                            </div>
                        </button>
                    </div>

                    {/* Content */}
                    <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)] custom-scrollbar">
                        {activeTab === 'comparison' && (
                            <>
                                {loading && (
                                    <div className="flex flex-col items-center justify-center py-12">
                                        <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
                                        <p className="text-muted-foreground">Comparing branches...</p>
                                    </div>
                                )}

                                {error && (
                                    <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
                                        <AlertTriangle className="h-5 w-5" />
                                        <span>{error}</span>
                                    </div>
                                )}

                                {comparison && !loading && (
                                    <div className="space-y-6">
                                        {/* Overall Score Comparison */}
                                        <div className="glass-card rounded-xl p-6">
                                            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                                                Overall Score Comparison
                                            </h3>
                                            <div className="flex items-center justify-center">
                                                <div className={cn(
                                                    "text-4xl font-bold px-6 py-3 rounded-lg border",
                                                    comparison.score_diff.overall_score_diff > 0
                                                        ? "text-green-400 bg-green-500/10 border-green-500/20"
                                                        : comparison.score_diff.overall_score_diff < 0
                                                        ? "text-red-400 bg-red-500/10 border-red-500/20"
                                                        : "text-gray-400 bg-gray-500/10 border-gray-500/20"
                                                )}>
                                                    {formatScoreDiff(comparison.score_diff.overall_score_diff)}
                                                </div>
                                            </div>
                                            <p className="text-center text-sm text-muted-foreground mt-2">
                                                {comparison.score_diff.overall_score_diff > 0 
                                                    ? `${compareBranch} scores ${comparison.score_diff.overall_score_diff.toFixed(1)} points higher`
                                                    : comparison.score_diff.overall_score_diff < 0
                                                    ? `${compareBranch} scores ${Math.abs(comparison.score_diff.overall_score_diff).toFixed(1)} points lower`
                                                    : 'Both branches have identical scores'
                                                }
                                            </p>
                                        </div>

                                        {/* Category Score Differences */}
                                        <div className="glass-card rounded-xl p-6">
                                            <h3 className="text-lg font-semibold mb-4">Category Breakdown</h3>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                {Object.entries(comparison.score_diff.category_diffs).map(([category, diff]) => (
                                                    <div key={category} className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/10">
                                                        <span className="capitalize text-sm font-medium">{category.replace('_', ' ')}</span>
                                                        <span className={cn(
                                                            "text-sm font-mono px-2 py-1 rounded border",
                                                            diff > 0
                                                                ? "text-green-400 bg-green-500/10 border-green-500/20"
                                                                : diff < 0
                                                                ? "text-red-400 bg-red-500/10 border-red-500/20"
                                                                : "text-gray-400 bg-gray-500/10 border-gray-500/20"
                                                        )}>
                                                            {formatScoreDiff(diff)}
                                                        </span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Quality Changes */}
                                        {comparison.quality_changes && comparison.quality_changes.length > 0 && (
                                            <div className="glass-card rounded-xl p-6">
                                                <h3 className="text-lg font-semibold mb-4">Quality Changes</h3>
                                                <div className="space-y-3">
                                                    {comparison.quality_changes.map((change, index) => (
                                                        <div key={index} className={cn(
                                                            "p-4 rounded-lg border",
                                                            getChangeColor(change.change_type)
                                                        )}>
                                                            <div className="flex items-start gap-3">
                                                                {getChangeIcon(change.change_type)}
                                                                <div className="flex-1">
                                                                    <div className="flex items-center gap-2 mb-1">
                                                                        <span className="font-medium capitalize">
                                                                            {change.category.replace('_', ' ')}
                                                                        </span>
                                                                        <span className="text-xs px-2 py-0.5 rounded bg-black/20">
                                                                            {change.change_type.toLowerCase()}
                                                                        </span>
                                                                    </div>
                                                                    <p className="text-sm mb-2">{change.description}</p>
                                                                    {change.affected_files.length > 0 && (
                                                                        <div className="text-xs text-muted-foreground">
                                                                            <span className="font-medium">Affected files: </span>
                                                                            {change.affected_files.slice(0, 3).join(', ')}
                                                                            {change.affected_files.length > 3 && ` and ${change.affected_files.length - 3} more`}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Recommendations */}
                                        {comparison.recommendations && comparison.recommendations.length > 0 && (
                                            <div className="glass-card rounded-xl p-6">
                                                <h3 className="text-lg font-semibold mb-4">Recommendations</h3>
                                                <div className="space-y-2">
                                                    {comparison.recommendations.map((recommendation, index) => (
                                                        <div key={index} className="flex items-start gap-3 p-3 bg-white/5 rounded-lg border border-white/10">
                                                            <div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0" />
                                                            <span className="text-sm">{recommendation}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </>
                        )}

                        {activeTab === 'trends' && (
                            <div className="space-y-6">
                                {/* Base Branch Trends */}
                                <div>
                                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                                        <Calendar className="h-5 w-5 text-primary" />
                                        {baseBranch} Branch Trends
                                    </h3>
                                    <HistoricalTrendChart
                                        repoId={repoId}
                                        branchName={baseBranch}
                                        daysBack={30}
                                    />
                                </div>

                                {/* Compare Branch Trends */}
                                <div>
                                    <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                                        <Calendar className="h-5 w-5 text-primary" />
                                        {compareBranch} Branch Trends
                                    </h3>
                                    <HistoricalTrendChart
                                        repoId={repoId}
                                        branchName={compareBranch}
                                        daysBack={30}
                                    />
                                </div>
                            </div>
                        )}
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    )
}
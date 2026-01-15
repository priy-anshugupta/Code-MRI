'use client'

import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    TimeScale,
    ChartOptions,
    TooltipItem
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import 'chartjs-adapter-date-fns'
import { 
    TrendingUp, 
    TrendingDown, 
    Minus, 
    Calendar, 
    BarChart3, 
    Loader2, 
    AlertTriangle,
    RefreshCw
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

// Register Chart.js components
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    TimeScale
)

interface HistoricalDataPoint {
    timestamp: string
    commit_sha: string
    branch_name: string
    overall_score: number
    category_scores: Record<string, number>
    total_files: number
    total_loc: number
}

interface TrendMetrics {
    direction: 'improving' | 'declining' | 'stable' | 'volatile'
    slope: number
    correlation: number
    volatility: number
    confidence: number
    start_value: number
    end_value: number
    total_change: number
}

interface CategoryTrend {
    category: string
    metrics: TrendMetrics
    data_points: Array<{
        timestamp: string
        score: number
    }>
}

interface BranchTrendAnalysis {
    repo_id: string
    branch_name: string
    analysis_period: {
        start: string
        end: string
    }
    overall_trend: TrendMetrics
    category_trends: Record<string, CategoryTrend>
    data_points: HistoricalDataPoint[]
    summary: string
}

interface VisualizationData {
    chart_type: string
    title: string
    x_axis_label: string
    y_axis_label: string
    datasets: Array<{
        label: string
        data: Array<{
            x: string
            y: number
        }>
        borderColor: string
        backgroundColor: string
        fill?: boolean
        tension?: number
    }>
    annotations: Array<{
        type: string
        xValue: string
        yValue: number
        backgroundColor: string
        label: {
            content: string
            enabled: boolean
        }
    }>
}

interface HistoricalTrendChartProps {
    repoId: string
    branchName: string
    daysBack?: number
    className?: string
}

const getTrendIcon = (direction: string) => {
    switch (direction) {
        case 'improving':
            return TrendingUp
        case 'declining':
            return TrendingDown
        case 'volatile':
            return BarChart3
        default:
            return Minus
    }
}

const getTrendColor = (direction: string) => {
    switch (direction) {
        case 'improving':
            return 'text-green-400'
        case 'declining':
            return 'text-red-400'
        case 'volatile':
            return 'text-orange-400'
        default:
            return 'text-gray-400'
    }
}

export const HistoricalTrendChart: React.FC<HistoricalTrendChartProps> = ({
    repoId,
    branchName,
    daysBack = 30,
    className
}) => {
    const [trendAnalysis, setTrendAnalysis] = useState<BranchTrendAnalysis | null>(null)
    const [visualizations, setVisualizations] = useState<VisualizationData[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string>('')
    const [selectedVisualization, setSelectedVisualization] = useState(0)
    const [hasFetched, setHasFetched] = useState(false)

    useEffect(() => {
        if (repoId && branchName && !hasFetched) {
            fetchTrendData()
        }
    }, [repoId, branchName, daysBack]) // eslint-disable-line react-hooks/exhaustive-deps

    const fetchTrendData = async () => {
        setLoading(true)
        setError('')
        setHasFetched(true)
        
        try {
            // Fetch trend analysis
            const trendResponse = await api.get(`/historical-trends/${repoId}/${branchName}`, {
                params: { days_back: daysBack }
            })
            
            // Check if we have data
            if (!trendResponse.data.has_data || !trendResponse.data.analysis) {
                // This is not an error, just no data yet - use the empty state instead
                setTrendAnalysis(null)
                setVisualizations([])
                setLoading(false)
                return
            }
            
            const analysis = trendResponse.data.analysis as BranchTrendAnalysis
            setTrendAnalysis(analysis)
            
            // Fetch visualization data
            const vizResponse = await api.get(`/historical-trends/${repoId}/${branchName}/visualizations`, {
                params: { days_back: daysBack, chart_type: 'line' }
            })
            
            // Check if we have visualization data
            if (!vizResponse.data.has_data || !vizResponse.data.visualizations || vizResponse.data.visualizations.length === 0) {
                // This is not an error, just no data yet - use the empty state instead
                setTrendAnalysis(null)
                setVisualizations([])
                setLoading(false)
                return
            }
            
            setVisualizations(vizResponse.data.visualizations as VisualizationData[])
            
        } catch (err: any) {
            console.error('Failed to fetch trend data:', err)
            // Handle 404 specifically (feature not yet implemented)
            if (err.response?.status === 404) {
                setError('Historical trend data not available yet. This feature requires multiple analyses over time.')
            } else {
                setError(err.response?.data?.detail || 'Failed to load historical trend data')
            }
        } finally {
            setLoading(false)
        }
    }

    const createChartOptions = (visualization: VisualizationData): ChartOptions<'line'> => {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index' as const,
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top' as const,
                    labels: {
                        color: '#9CA3AF',
                        font: {
                            size: 12
                        }
                    }
                },
                title: {
                    display: true,
                    text: visualization.title,
                    color: '#F3F4F6',
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#F3F4F6',
                    bodyColor: '#D1D5DB',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context: TooltipItem<'line'>) {
                            const label = context.dataset.label || ''
                            const value = typeof context.parsed.y === 'number' ? context.parsed.y.toFixed(1) : context.parsed.y
                            return `${label}: ${value}`
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time' as const,
                    time: {
                        displayFormats: {
                            day: 'MMM dd',
                            week: 'MMM dd',
                            month: 'MMM yyyy'
                        }
                    },
                    title: {
                        display: true,
                        text: visualization.x_axis_label,
                        color: '#9CA3AF'
                    },
                    ticks: {
                        color: '#6B7280'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: visualization.y_axis_label,
                        color: '#9CA3AF'
                    },
                    ticks: {
                        color: '#6B7280'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                }
            },
            elements: {
                point: {
                    radius: 4,
                    hoverRadius: 6
                },
                line: {
                    tension: 0.4
                }
            }
        }
    }

    const formatTrendSummary = (trend: TrendMetrics) => {
        const changeText = trend.total_change > 0 ? 
            `+${trend.total_change.toFixed(1)}` : 
            trend.total_change.toFixed(1)
        
        const confidenceText = `${(trend.confidence * 100).toFixed(0)}% confidence`
        
        return `${changeText} points (${confidenceText})`
    }

    if (loading) {
        return (
            <div className={cn("glass-card rounded-xl p-6", className)}>
                <div className="flex flex-col items-center justify-center py-12">
                    <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
                    <p className="text-muted-foreground">Loading historical trends...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className={cn("glass-card rounded-xl p-6", className)}>
                <div className="flex flex-col items-center justify-center py-12">
                    <AlertTriangle className="h-12 w-12 text-red-400 mb-4" />
                    <p className="text-red-400 text-center mb-4">{error}</p>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={fetchTrendData}
                        className="gap-2"
                    >
                        <RefreshCw className="h-4 w-4" />
                        Retry
                    </Button>
                </div>
            </div>
        )
    }

    if (!trendAnalysis || visualizations.length === 0) {
        return (
            <div className={cn("glass-card rounded-xl p-6", className)}>
                <div className="flex flex-col items-center justify-center py-12">
                    <BarChart3 className="h-12 w-12 text-muted-foreground/50 mb-4" />
                    <p className="text-muted-foreground text-center">
                        No historical data available for this branch.
                    </p>
                    <p className="text-sm text-muted-foreground/60 mt-2">
                        Trends will appear after multiple analyses over time.
                    </p>
                </div>
            </div>
        )
    }

    const currentVisualization = visualizations[selectedVisualization]
    const TrendIcon = getTrendIcon(trendAnalysis.overall_trend.direction)

    return (
        <div className={cn("glass-card rounded-xl overflow-hidden", className)}>
            {/* Header */}
            <div className="p-6 border-b border-white/10 bg-white/5">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-primary/10">
                            <BarChart3 className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <h3 className="text-lg font-semibold">Historical Trends</h3>
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Calendar className="w-4 h-4" />
                                <span>
                                    {new Date(trendAnalysis.analysis_period.start).toLocaleDateString()} - {' '}
                                    {new Date(trendAnalysis.analysis_period.end).toLocaleDateString()}
                                </span>
                                <span>•</span>
                                <span>{trendAnalysis.data_points.length} data points</span>
                            </div>
                        </div>
                    </div>
                    
                    <div className="flex items-center gap-4">
                        {/* Overall Trend Indicator */}
                        <div className="flex items-center gap-2">
                            <TrendIcon className={cn("w-5 h-5", getTrendColor(trendAnalysis.overall_trend.direction))} />
                            <div className="text-right">
                                <div className="text-sm font-medium capitalize">
                                    {trendAnalysis.overall_trend.direction}
                                </div>
                                <div className="text-xs text-muted-foreground">
                                    {formatTrendSummary(trendAnalysis.overall_trend)}
                                </div>
                            </div>
                        </div>
                        
                        {/* Visualization Selector */}
                        {visualizations.length > 1 && (
                            <div className="flex gap-1">
                                {visualizations.map((_, index) => (
                                    <Button
                                        key={index}
                                        variant={selectedVisualization === index ? "default" : "ghost"}
                                        size="sm"
                                        onClick={() => setSelectedVisualization(index)}
                                        className="px-3"
                                    >
                                        {index === 0 ? 'Overall' : index === 1 ? 'Categories' : 'Metrics'}
                                    </Button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Chart */}
            <div className="p-6">
                <div className="h-80 mb-6">
                    <Line
                        data={{
                            datasets: currentVisualization.datasets.map(dataset => ({
                                ...dataset,
                                data: dataset.data.map(point => ({
                                    x: point.x,
                                    y: point.y
                                }))
                            }))
                        }}
                        options={createChartOptions(currentVisualization)}
                    />
                </div>

                {/* Summary */}
                <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                    <h4 className="text-sm font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                        Analysis Summary
                    </h4>
                    <p className="text-sm leading-relaxed">{trendAnalysis.summary}</p>
                </div>

                {/* Category Trends */}
                {Object.keys(trendAnalysis.category_trends).length > 0 && (
                    <div className="mt-6">
                        <h4 className="text-sm font-medium text-muted-foreground mb-4 uppercase tracking-wider">
                            Category Trends
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {Object.entries(trendAnalysis.category_trends).map(([category, trend]) => {
                                const CategoryTrendIcon = getTrendIcon(trend.metrics.direction)
                                return (
                                    <motion.div
                                        key={category}
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="bg-white/5 rounded-lg p-4 border border-white/10"
                                    >
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-sm font-medium capitalize">
                                                {category.replace('_', ' ')}
                                            </span>
                                            <CategoryTrendIcon className={cn(
                                                "w-4 h-4", 
                                                getTrendColor(trend.metrics.direction)
                                            )} />
                                        </div>
                                        <div className="text-xs text-muted-foreground">
                                            {formatTrendSummary(trend.metrics)}
                                        </div>
                                        <div className="text-xs text-muted-foreground/60 mt-1 capitalize">
                                            {trend.metrics.direction}
                                        </div>
                                    </motion.div>
                                )
                            })}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

export default HistoricalTrendChart
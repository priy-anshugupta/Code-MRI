'use client'

import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { 
    BarChart3, 
    Calendar, 
    GitBranch, 
    TrendingUp,
    Settings,
    RefreshCw
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { HistoricalTrendChart } from './HistoricalTrendChart'
import { cn } from '@/lib/utils'

interface HistoricalTrendsPanelProps {
    repoId: string
    currentBranch: string
    branches: Array<{
        name: string
        is_default: boolean
    }>
    className?: string
}

export const HistoricalTrendsPanel: React.FC<HistoricalTrendsPanelProps> = ({
    repoId,
    currentBranch,
    branches,
    className
}) => {
    const [selectedBranch, setSelectedBranch] = useState(currentBranch)
    const [daysBack, setDaysBack] = useState(30)
    const [refreshKey, setRefreshKey] = useState(0)

    const handleRefresh = () => {
        setRefreshKey(prev => prev + 1)
    }

    const timeRangeOptions = [
        { label: '7 days', value: 7 },
        { label: '30 days', value: 30 },
        { label: '90 days', value: 90 },
        { label: '180 days', value: 180 }
    ]

    return (
        <div className={cn("space-y-6", className)}>
            {/* Header */}
            <div className="glass-card rounded-xl p-6">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-primary/10">
                            <BarChart3 className="w-6 h-6 text-primary" />
                        </div>
                        <div>
                            <h2 className="text-xl font-semibold">Historical Quality Trends</h2>
                            <p className="text-sm text-muted-foreground mt-1">
                                Track code quality evolution over time across branches
                            </p>
                        </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                        {/* Time Range Selector */}
                        <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4 text-muted-foreground" />
                            <select
                                value={daysBack}
                                onChange={(e) => setDaysBack(Number(e.target.value))}
                                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                            >
                                {timeRangeOptions.map(option => (
                                    <option key={option.value} value={option.value}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        
                        {/* Branch Selector */}
                        {branches.length > 1 && (
                            <div className="flex items-center gap-2">
                                <GitBranch className="w-4 h-4 text-muted-foreground" />
                                <select
                                    value={selectedBranch}
                                    onChange={(e) => setSelectedBranch(e.target.value)}
                                    className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 font-mono"
                                >
                                    {branches.map(branch => (
                                        <option key={branch.name} value={branch.name}>
                                            {branch.name} {branch.is_default ? '(default)' : ''}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}
                        
                        {/* Refresh Button */}
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleRefresh}
                            className="gap-2"
                        >
                            <RefreshCw className="w-4 h-4" />
                            Refresh
                        </Button>
                    </div>
                </div>
            </div>

            {/* Trend Chart */}
            <HistoricalTrendChart
                key={`${selectedBranch}-${daysBack}-${refreshKey}`}
                repoId={repoId}
                branchName={selectedBranch}
                daysBack={daysBack}
            />

            {/* Multi-Branch Comparison */}
            {branches.length > 1 && (
                <div className="glass-card rounded-xl p-6">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h3 className="text-lg font-semibold flex items-center gap-2">
                                <TrendingUp className="w-5 h-5 text-primary" />
                                Branch Comparison
                            </h3>
                            <p className="text-sm text-muted-foreground mt-1">
                                Compare quality trends across different branches
                            </p>
                        </div>
                    </div>
                    
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {branches.slice(0, 2).map((branch, index) => (
                            <motion.div
                                key={branch.name}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.1 }}
                            >
                                <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                                    <div className="flex items-center gap-2 mb-4">
                                        <GitBranch className="w-4 h-4 text-primary" />
                                        <span className="font-mono font-medium">{branch.name}</span>
                                        {branch.is_default && (
                                            <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded border border-primary/30">
                                                DEFAULT
                                            </span>
                                        )}
                                    </div>
                                    
                                    <HistoricalTrendChart
                                        key={`comparison-${branch.name}-${daysBack}-${refreshKey}`}
                                        repoId={repoId}
                                        branchName={branch.name}
                                        daysBack={daysBack}
                                        className="h-64"
                                    />
                                </div>
                            </motion.div>
                        ))}
                    </div>
                    
                    {branches.length > 2 && (
                        <div className="mt-4 text-center">
                            <p className="text-sm text-muted-foreground">
                                {branches.length - 2} more branch{branches.length > 3 ? 'es' : ''} available. 
                                Use the branch selector above to view individual trends.
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Insights Panel */}
            <div className="glass-card rounded-xl p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Settings className="w-5 h-5 text-primary" />
                    Trend Analysis Insights
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                        <div className="text-sm font-medium text-muted-foreground mb-2">Data Collection</div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Historical data is collected each time a branch is analyzed. 
                            More frequent analyses provide better trend accuracy.
                        </p>
                    </div>
                    
                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                        <div className="text-sm font-medium text-muted-foreground mb-2">Trend Confidence</div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Confidence levels indicate how reliable the trend analysis is. 
                            Higher confidence requires more data points and consistent patterns.
                        </p>
                    </div>
                    
                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                        <div className="text-sm font-medium text-muted-foreground mb-2">Quality Metrics</div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                            Trends track overall quality scores and individual category scores 
                            including readability, complexity, maintainability, and security.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default HistoricalTrendsPanel
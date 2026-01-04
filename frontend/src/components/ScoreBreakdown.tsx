'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { 
    BookOpen, 
    Cpu, 
    Layers, 
    FileText, 
    Shield, 
    Zap,
    TrendingUp,
    TrendingDown,
    Minus,
    ChevronRight,
    Info,
    AlertCircle,
    CheckCircle2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

// Types for score data
interface CategoryScore {
    name: string
    score: number
    weight: number
    contributing_factors: string[]
    improvement_potential: number
}

interface Recommendation {
    category: string
    priority: 'HIGH' | 'MEDIUM' | 'LOW'
    title: string
    description: string
    estimated_impact: number
    effort_level: 'EASY' | 'MODERATE' | 'HARD'
    specific_files: string[]
}

interface DetailedScoreReport {
    overall_grade: string
    overall_score: number
    category_scores: Record<string, CategoryScore>
    recommendations: Recommendation[]
    trends?: {
        overall_trend: 'up' | 'down' | 'stable'
        category_trends: Record<string, 'up' | 'down' | 'stable'>
    }
}

interface ScoreBreakdownProps {
    scoreData: DetailedScoreReport
    onExplainScore?: (category: string) => void
    showTrends?: boolean
}

// Category icons and colors
const categoryConfig = {
    readability: {
        icon: BookOpen,
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/10',
        borderColor: 'border-blue-500/20',
        label: 'Readability'
    },
    complexity: {
        icon: Cpu,
        color: 'text-purple-400',
        bgColor: 'bg-purple-500/10',
        borderColor: 'border-purple-500/20',
        label: 'Complexity'
    },
    maintainability: {
        icon: Layers,
        color: 'text-green-400',
        bgColor: 'bg-green-500/10',
        borderColor: 'border-green-500/20',
        label: 'Maintainability'
    },
    documentation: {
        icon: FileText,
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-500/10',
        borderColor: 'border-yellow-500/20',
        label: 'Documentation'
    },
    security: {
        icon: Shield,
        color: 'text-red-400',
        bgColor: 'bg-red-500/10',
        borderColor: 'border-red-500/20',
        label: 'Security'
    },
    performance: {
        icon: Zap,
        color: 'text-orange-400',
        bgColor: 'bg-orange-500/10',
        borderColor: 'border-orange-500/20',
        label: 'Performance'
    }
}

// Score color helper
const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-400'
    if (score >= 80) return 'text-blue-400'
    if (score >= 70) return 'text-yellow-400'
    if (score >= 60) return 'text-orange-400'
    return 'text-red-400'
}

// Trend icon helper
const getTrendIcon = (trend: 'up' | 'down' | 'stable') => {
    switch (trend) {
        case 'up': return TrendingUp
        case 'down': return TrendingDown
        default: return Minus
    }
}

// Individual category score component
const CategoryScoreCard: React.FC<{
    category: string
    score: CategoryScore
    trend?: 'up' | 'down' | 'stable'
    onExplain?: () => void
    isExpanded?: boolean
    onToggleExpand?: () => void
}> = ({ category, score, trend, onExplain, isExpanded, onToggleExpand }) => {
    const config = categoryConfig[category as keyof typeof categoryConfig]
    if (!config) return null

    const Icon = config.icon
    const TrendIcon = trend ? getTrendIcon(trend) : null
    const scoreColor = getScoreColor(score.score)

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                "glass-card rounded-xl p-6 border transition-all duration-300 hover:border-primary/30",
                config.borderColor
            )}
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className={cn("p-2 rounded-lg", config.bgColor)}>
                        <Icon className={cn("w-5 h-5", config.color)} />
                    </div>
                    <div>
                        <h3 className="font-semibold text-foreground">{config.label}</h3>
                        <div className="flex items-center gap-2">
                            <span className={cn("text-2xl font-bold", scoreColor)}>
                                {score.score.toFixed(1)}
                            </span>
                            <span className="text-sm text-muted-foreground">/100</span>
                            {TrendIcon && (
                                <TrendIcon className={cn(
                                    "w-4 h-4",
                                    trend === 'up' ? 'text-green-400' : 
                                    trend === 'down' ? 'text-red-400' : 'text-muted-foreground'
                                )} />
                            )}
                        </div>
                    </div>
                </div>
                
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                        Weight: {(score.weight * 100).toFixed(0)}%
                    </span>
                    {onToggleExpand && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={onToggleExpand}
                            className="h-8 w-8 p-0"
                        >
                            <ChevronRight className={cn(
                                "w-4 h-4 transition-transform",
                                isExpanded && "rotate-90"
                            )} />
                        </Button>
                    )}
                </div>
            </div>

            {/* Score Bar */}
            <div className="mb-4">
                <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                    <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${score.score}%` }}
                        transition={{ duration: 1, ease: "easeOut" }}
                        className={cn(
                            "h-full rounded-full",
                            score.score >= 90 ? 'bg-green-400' :
                            score.score >= 80 ? 'bg-blue-400' :
                            score.score >= 70 ? 'bg-yellow-400' :
                            score.score >= 60 ? 'bg-orange-400' : 'bg-red-400'
                        )}
                    />
                </div>
            </div>

            {/* Expanded Details */}
            {isExpanded && (
                <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-4"
                >
                    {/* Contributing Factors */}
                    {score.contributing_factors.length > 0 && (
                        <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2 flex items-center gap-2">
                                <Info className="w-3 h-3" />
                                Contributing Factors
                            </h4>
                            <div className="space-y-1">
                                {score.contributing_factors.map((factor, index) => (
                                    <div key={index} className="text-xs text-muted-foreground flex items-start gap-2">
                                        <span className="w-1 h-1 rounded-full bg-muted-foreground mt-2 flex-shrink-0" />
                                        {factor}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Improvement Potential */}
                    {score.improvement_potential > 0 && (
                        <div>
                            <h4 className="text-sm font-medium text-muted-foreground mb-2">
                                Improvement Potential
                            </h4>
                            <div className="flex items-center gap-2">
                                <div className="flex-1 bg-white/5 rounded-full h-1.5">
                                    <div 
                                        className="h-full bg-primary rounded-full"
                                        style={{ width: `${Math.min(100, score.improvement_potential)}%` }}
                                    />
                                </div>
                                <span className="text-xs text-primary font-medium">
                                    +{score.improvement_potential.toFixed(1)}
                                </span>
                            </div>
                        </div>
                    )}

                    {/* Explain Button */}
                    {onExplain && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onExplain}
                            className="w-full gap-2"
                        >
                            <Info className="w-4 h-4" />
                            Explain Score
                        </Button>
                    )}
                </motion.div>
            )}
        </motion.div>
    )
}

// Recommendations component
const RecommendationsPanel: React.FC<{
    recommendations: Recommendation[]
    onViewRecommendation?: (recommendation: Recommendation) => void
}> = ({ recommendations, onViewRecommendation }) => {
    const priorityConfig = {
        HIGH: { color: 'text-red-400', bgColor: 'bg-red-500/10', borderColor: 'border-red-500/20' },
        MEDIUM: { color: 'text-yellow-400', bgColor: 'bg-yellow-500/10', borderColor: 'border-yellow-500/20' },
        LOW: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500/20' }
    }

    const effortConfig = {
        EASY: { icon: CheckCircle2, color: 'text-green-400' },
        MODERATE: { icon: AlertCircle, color: 'text-yellow-400' },
        HARD: { icon: AlertCircle, color: 'text-red-400' }
    }

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                Improvement Recommendations
            </h3>
            
            {recommendations.length === 0 ? (
                <div className="glass-card rounded-xl p-6 text-center">
                    <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-green-500/50" />
                    <p className="text-muted-foreground">No specific recommendations at this time.</p>
                    <p className="text-sm text-muted-foreground/60 mt-1">Your code quality is looking good!</p>
                </div>
            ) : (
                <div className="space-y-3">
                    {recommendations.map((rec, index) => {
                        const priorityStyle = priorityConfig[rec.priority]
                        const effortStyle = effortConfig[rec.effort_level]
                        const EffortIcon = effortStyle.icon

                        return (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: index * 0.1 }}
                                className={cn(
                                    "glass-card rounded-xl p-4 border transition-all duration-300 hover:border-primary/30",
                                    priorityStyle.borderColor
                                )}
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className={cn(
                                                "px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider border",
                                                priorityStyle.color,
                                                priorityStyle.bgColor,
                                                priorityStyle.borderColor
                                            )}>
                                                {rec.priority}
                                            </span>
                                            <span className="text-xs text-muted-foreground">
                                                {rec.category}
                                            </span>
                                        </div>
                                        
                                        <h4 className="font-medium text-foreground mb-1">{rec.title}</h4>
                                        <p className="text-sm text-muted-foreground mb-3">{rec.description}</p>
                                        
                                        <div className="flex items-center gap-4 text-xs">
                                            <div className="flex items-center gap-1">
                                                <EffortIcon className={cn("w-3 h-3", effortStyle.color)} />
                                                <span className="text-muted-foreground">{rec.effort_level}</span>
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <TrendingUp className="w-3 h-3 text-primary" />
                                                <span className="text-muted-foreground">
                                                    +{rec.estimated_impact.toFixed(1)} impact
                                                </span>
                                            </div>
                                            {rec.specific_files.length > 0 && (
                                                <span className="text-muted-foreground">
                                                    {rec.specific_files.length} file{rec.specific_files.length > 1 ? 's' : ''}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    
                                    {onViewRecommendation && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => onViewRecommendation(rec)}
                                            className="flex-shrink-0"
                                        >
                                            <ChevronRight className="w-4 h-4" />
                                        </Button>
                                    )}
                                </div>
                            </motion.div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}

// Main score breakdown component
export const ScoreBreakdown: React.FC<ScoreBreakdownProps> = ({
    scoreData,
    onExplainScore,
    showTrends = false
}) => {
    const [expandedCategories, setExpandedCategories] = React.useState<Set<string>>(new Set())

    const toggleExpanded = (category: string) => {
        const newExpanded = new Set(expandedCategories)
        if (newExpanded.has(category)) {
            newExpanded.delete(category)
        } else {
            newExpanded.add(category)
        }
        setExpandedCategories(newExpanded)
    }

    const handleExplainScore = (category: string) => {
        if (onExplainScore) {
            onExplainScore(category)
        }
    }

    return (
        <div className="space-y-6">
            {/* Overall Score Header */}
            <div className="glass-card rounded-xl p-6 text-center">
                <div className="flex items-center justify-center gap-4 mb-4">
                    <div className={cn(
                        "w-20 h-20 rounded-full border-4 flex items-center justify-center",
                        getScoreColor(scoreData.overall_score),
                        scoreData.overall_score >= 90 ? 'border-green-500/50 shadow-[0_0_30px_rgba(74,222,128,0.2)]' :
                        scoreData.overall_score >= 80 ? 'border-blue-500/50 shadow-[0_0_30px_rgba(96,165,250,0.2)]' :
                        scoreData.overall_score >= 70 ? 'border-yellow-500/50 shadow-[0_0_30px_rgba(250,204,21,0.2)]' :
                        'border-red-500/50 shadow-[0_0_30px_rgba(248,113,113,0.2)]'
                    )}>
                        <div className="text-center">
                            <div className="text-2xl font-bold">{scoreData.overall_grade}</div>
                            <div className="text-xs opacity-70">GRADE</div>
                        </div>
                    </div>
                    
                    <div className="text-left">
                        <div className="text-3xl font-bold text-foreground">
                            {scoreData.overall_score.toFixed(1)}
                        </div>
                        <div className="text-sm text-muted-foreground">Overall Score</div>
                        {showTrends && scoreData.trends && (
                            <div className="flex items-center gap-1 mt-1">
                                {React.createElement(getTrendIcon(scoreData.trends.overall_trend), {
                                    className: cn(
                                        "w-4 h-4",
                                        scoreData.trends.overall_trend === 'up' ? 'text-green-400' :
                                        scoreData.trends.overall_trend === 'down' ? 'text-red-400' : 'text-muted-foreground'
                                    )
                                })}
                                <span className="text-xs text-muted-foreground">
                                    {scoreData.trends.overall_trend === 'up' ? 'Improving' :
                                     scoreData.trends.overall_trend === 'down' ? 'Declining' : 'Stable'}
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Category Scores Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(scoreData.category_scores).map(([category, score]) => (
                    <CategoryScoreCard
                        key={category}
                        category={category}
                        score={score}
                        trend={showTrends ? scoreData.trends?.category_trends[category] : undefined}
                        onExplain={() => handleExplainScore(category)}
                        isExpanded={expandedCategories.has(category)}
                        onToggleExpand={() => toggleExpanded(category)}
                    />
                ))}
            </div>

            {/* Recommendations */}
            <RecommendationsPanel
                recommendations={scoreData.recommendations}
                onViewRecommendation={(rec) => {
                    // Could open a modal or navigate to detailed view
                    console.log('View recommendation:', rec)
                }}
            />
        </div>
    )
}

export default ScoreBreakdown
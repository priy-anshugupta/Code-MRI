'use client'

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
    X, 
    Brain, 
    Loader2, 
    AlertTriangle, 
    RefreshCw,
    MessageSquare,
    Lightbulb,
    TrendingUp,
    FileCode,
    Clock
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useErrorHandler } from '@/hooks/useErrorHandler'
import { ErrorFallback } from './ErrorFallback'

interface AIExplanationModalProps {
    isOpen: boolean
    onClose: () => void
    repoId: string
    explanationType: 'grading' | 'code' | 'comparison'
    context: {
        category?: string
        filePath?: string
        branchComparison?: {
            baseBranch: string
            compareBranch: string
        }
        scoreData?: any
    }
}

interface ExplanationResponse {
    explanation: string
    key_insights: string[]
    recommendations?: string[]
    confidence_level: 'high' | 'medium' | 'low'
    processing_time: number
    fallback_used: boolean
}

interface ExplanationState {
    loading: boolean
    data: ExplanationResponse | null
    error: string | null
    retryCount: number
}

const ExplanationTypeConfig = {
    grading: {
        icon: TrendingUp,
        title: 'Grading Explanation',
        description: 'Understanding your code quality scores',
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/10',
        borderColor: 'border-blue-500/20'
    },
    code: {
        icon: FileCode,
        title: 'Code Analysis',
        description: 'AI insights about your code structure',
        color: 'text-green-400',
        bgColor: 'bg-green-500/10',
        borderColor: 'border-green-500/20'
    },
    comparison: {
        icon: MessageSquare,
        title: 'Branch Comparison',
        description: 'Understanding differences between branches',
        color: 'text-purple-400',
        bgColor: 'bg-purple-500/10',
        borderColor: 'border-purple-500/20'
    }
}

const LoadingStates = [
    "Analyzing code patterns...",
    "Processing quality metrics...",
    "Generating insights...",
    "Preparing explanation...",
    "Almost ready..."
]

const FallbackExplanations = {
    grading: {
        explanation: "Your code quality score is calculated based on multiple factors including readability, complexity, maintainability, documentation, security, and performance. Each category is weighted according to industry best practices.",
        key_insights: [
            "Scores are calculated using static analysis tools",
            "Higher scores indicate better code quality",
            "Each category contributes to the overall grade"
        ]
    },
    code: {
        explanation: "This code file has been analyzed for structure, patterns, and quality indicators. The analysis includes complexity metrics, documentation coverage, and potential improvement areas.",
        key_insights: [
            "Code structure affects maintainability",
            "Documentation improves code understanding",
            "Lower complexity generally indicates better code"
        ]
    },
    comparison: {
        explanation: "Branch comparison shows differences in code quality metrics between the selected branches. This helps identify improvements or regressions in code quality.",
        key_insights: [
            "Quality differences highlight code evolution",
            "Improvements indicate positive development",
            "Regressions may need attention"
        ]
    }
}

export const AIExplanationModal: React.FC<AIExplanationModalProps> = ({
    isOpen,
    onClose,
    repoId,
    explanationType,
    context
}) => {
    const [data, setData] = useState<ExplanationResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [loadingMessageIndex, setLoadingMessageIndex] = useState(0)
    
    const errorHandler = useErrorHandler({
        maxRetries: 1,
        retryDelay: 3000
    })

    const config = ExplanationTypeConfig[explanationType]
    const Icon = config.icon

    // Cycle through loading messages
    useEffect(() => {
        if (!loading) return

        const interval = setInterval(() => {
            setLoadingMessageIndex(prev => (prev + 1) % LoadingStates.length)
        }, 2000)

        return () => clearInterval(interval)
    }, [loading])

    // Fetch explanation when modal opens
    useEffect(() => {
        if (isOpen && !data && !loading) {
            fetchExplanation()
        }
    }, [isOpen])

    const fetchExplanation = async () => {
        setLoading(true)
        errorHandler.clearError()

        try {
            const payload = {
                repo_id: repoId,
                explanation_type: explanationType,
                context: context
            }

            const response = await errorHandler.execute(() => 
                api.post('/explain', payload, { timeout: 120000 })
            )

            setData(response.data)
        } catch (error: any) {
            // Check if it's a rate limit error or timeout
            if (error?.response?.status === 429) {
                errorHandler.handleError(new Error('Rate limit reached. Please wait a moment before requesting another explanation.'))
            } else if (error?.code === 'ECONNABORTED') {
                errorHandler.handleError(new Error('Request timed out. The AI service may be busy.'))
            } else {
                // Use fallback explanation for other errors
                const fallback = FallbackExplanations[explanationType]
                setData({
                    explanation: fallback.explanation,
                    key_insights: fallback.key_insights,
                    confidence_level: 'low' as const,
                    processing_time: 0,
                    fallback_used: true
                })
            }
        } finally {
            setLoading(false)
        }
    }

    const handleRetry = () => {
        setData(null)
        errorHandler.clearError()
        fetchExplanation()
    }

    const handleClose = () => {
        setData(null)
        setLoading(false)
        errorHandler.clearError()
        setLoadingMessageIndex(0)
        onClose()
    }

    const getContextTitle = () => {
        switch (explanationType) {
            case 'grading':
                return context.category ? `${context.category} Score` : 'Overall Grading'
            case 'code':
                return context.filePath ? context.filePath.split('/').pop() : 'Code Analysis'
            case 'comparison':
                return context.branchComparison 
                    ? `${context.branchComparison.baseBranch} vs ${context.branchComparison.compareBranch}`
                    : 'Branch Comparison'
            default:
                return 'AI Explanation'
        }
    }

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
                        onClick={handleClose}
                    />

                    {/* Modal */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="relative w-full max-w-4xl max-h-[90vh] bg-background border border-white/10 rounded-2xl shadow-2xl overflow-hidden"
                    >
                        {/* Header */}
                        <div className={cn(
                            "p-6 border-b border-white/10",
                            config.bgColor
                        )}>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className={cn("p-3 rounded-xl", config.bgColor, config.borderColor, "border")}>
                                        <Icon className={cn("w-6 h-6", config.color)} />
                                    </div>
                                    <div>
                                        <h2 className="text-xl font-bold text-foreground">{config.title}</h2>
                                        <p className="text-sm text-muted-foreground">{config.description}</p>
                                        <p className="text-xs text-muted-foreground mt-1 font-mono">
                                            {getContextTitle()}
                                        </p>
                                    </div>
                                </div>
                                
                                <div className="flex items-center gap-2">
                                    {data && !loading && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={handleRetry}
                                            className="gap-2"
                                        >
                                            <RefreshCw className="w-4 h-4" />
                                            Refresh
                                        </Button>
                                    )}
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={handleClose}
                                        className="h-8 w-8 p-0"
                                    >
                                        <X className="w-4 h-4" />
                                    </Button>
                                </div>
                            </div>
                        </div>

                        {/* Content */}
                        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)] custom-scrollbar">
                            {/* Loading State */}
                            {loading && (
                                <div className="flex flex-col items-center justify-center py-12">
                                    <div className="relative mb-6">
                                        <Brain className="w-16 h-16 text-primary animate-pulse" />
                                        <div className="absolute -top-1 -right-1">
                                            <Loader2 className="w-6 h-6 animate-spin text-primary" />
                                        </div>
                                    </div>
                                    <div className="text-center">
                                        <p className="text-lg font-medium text-foreground mb-2">
                                            AI is thinking...
                                        </p>
                                        <p className="text-sm text-muted-foreground animate-pulse">
                                            {LoadingStates[loadingMessageIndex]}
                                        </p>
                                        <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
                                            <Clock className="w-3 h-3" />
                                            This may take up to 30 seconds
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Error State */}
                            {errorHandler.hasError && (
                                <div className="flex flex-col items-center justify-center py-12">
                                    <ErrorFallback
                                        error={errorHandler.error ? new Error(errorHandler.getErrorMessage() || 'Unknown error') : undefined}
                                        type={errorHandler.isNetworkError ? 'network' : 
                                              errorHandler.isAPIError ? 'api' : 
                                              errorHandler.isTimeoutError ? 'timeout' : 'ai'}
                                        resetErrorBoundary={handleRetry}
                                        showRetry={errorHandler.canRetry}
                                        title="AI Explanation Failed"
                                        size="md"
                                    />
                                </div>
                            )}

                            {/* Success State */}
                            {data && !loading && (
                                <div className="space-y-6">
                                    {/* Fallback Notice */}
                                    {data.fallback_used && (
                                        <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                                            <div className="flex items-center gap-2 text-yellow-400 mb-2">
                                                <AlertTriangle className="w-4 h-4" />
                                                <span className="font-medium">Limited AI Response</span>
                                            </div>
                                            <p className="text-sm text-muted-foreground">
                                                AI service is currently unavailable. Showing general explanation instead.
                                            </p>
                                        </div>
                                    )}

                                    {/* Main Explanation */}
                                    <div className="glass-card rounded-xl p-6">
                                        <div className="flex items-center gap-2 mb-4">
                                            <Brain className="w-5 h-5 text-primary" />
                                            <h3 className="font-semibold">AI Explanation</h3>
                                            {data.confidence_level && (
                                                <span className={cn(
                                                    "px-2 py-0.5 rounded text-xs font-medium",
                                                    data.confidence_level === 'high' ? 'bg-green-500/20 text-green-400' :
                                                    data.confidence_level === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                                    'bg-red-500/20 text-red-400'
                                                )}>
                                                    {data.confidence_level} confidence
                                                </span>
                                            )}
                                        </div>
                                        <div className="prose prose-invert max-w-none">
                                            <MarkdownRenderer content={data.explanation} />
                                        </div>
                                    </div>

                                    {/* Key Insights */}
                                    {data.key_insights && data.key_insights.length > 0 && (
                                        <div className="glass-card rounded-xl p-6">
                                            <div className="flex items-center gap-2 mb-4">
                                                <Lightbulb className="w-5 h-5 text-yellow-400" />
                                                <h3 className="font-semibold">Key Insights</h3>
                                            </div>
                                            <div className="space-y-3">
                                                {data.key_insights.map((insight, index) => (
                                                    <motion.div
                                                        key={index}
                                                        initial={{ opacity: 0, x: -20 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        transition={{ delay: index * 0.1 }}
                                                        className="flex items-start gap-3 p-3 bg-white/5 rounded-lg"
                                                    >
                                                        <div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0" />
                                                        <p className="text-sm text-muted-foreground">{insight}</p>
                                                    </motion.div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Recommendations */}
                                    {data.recommendations && data.recommendations.length > 0 && (
                                        <div className="glass-card rounded-xl p-6">
                                            <div className="flex items-center gap-2 mb-4">
                                                <TrendingUp className="w-5 h-5 text-green-400" />
                                                <h3 className="font-semibold">Recommendations</h3>
                                            </div>
                                            <div className="space-y-3">
                                                {data.recommendations.map((rec, index) => (
                                                    <motion.div
                                                        key={index}
                                                        initial={{ opacity: 0, x: -20 }}
                                                        animate={{ opacity: 1, x: 0 }}
                                                        transition={{ delay: index * 0.1 }}
                                                        className="flex items-start gap-3 p-3 bg-green-500/5 border border-green-500/20 rounded-lg"
                                                    >
                                                        <div className="w-2 h-2 rounded-full bg-green-400 mt-2 flex-shrink-0" />
                                                        <p className="text-sm text-muted-foreground">{rec}</p>
                                                    </motion.div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Processing Info */}
                                    {data.processing_time > 0 && (
                                        <div className="text-center text-xs text-muted-foreground">
                                            Generated in {data.processing_time.toFixed(1)}s
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    )
}

export default AIExplanationModal
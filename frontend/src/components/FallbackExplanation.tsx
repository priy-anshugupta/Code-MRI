'use client'

import React from 'react'
import { AlertTriangle, Info, Lightbulb } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FallbackExplanationProps {
    type: 'grading' | 'code' | 'comparison'
    category?: string
    className?: string
}

const fallbackContent = {
    grading: {
        title: 'Code Quality Assessment',
        explanation: 'Your code quality score is calculated based on multiple factors including readability, complexity, maintainability, documentation, security, and performance. Each category is weighted according to industry best practices.',
        insights: [
            'Scores are calculated using static analysis tools',
            'Higher scores indicate better code quality',
            'Each category contributes to the overall grade',
            'Regular monitoring helps track improvements over time'
        ]
    },
    code: {
        title: 'Code Analysis',
        explanation: 'This code file has been analyzed for structure, patterns, and quality indicators. The analysis includes complexity metrics, documentation coverage, and potential improvement areas.',
        insights: [
            'Code structure affects maintainability',
            'Documentation improves code understanding',
            'Lower complexity generally indicates better code',
            'Consistent patterns enhance readability'
        ]
    },
    comparison: {
        title: 'Branch Comparison',
        explanation: 'Branch comparison shows differences in code quality metrics between the selected branches. This helps identify improvements or regressions in code quality over time.',
        insights: [
            'Quality differences highlight code evolution',
            'Improvements indicate positive development',
            'Regressions may need attention',
            'Trends help guide development decisions'
        ]
    }
}

export const FallbackExplanation: React.FC<FallbackExplanationProps> = ({
    type,
    category,
    className
}) => {
    const content = fallbackContent[type]
    
    return (
        <div className={cn("space-y-4", className)}>
            {/* Notice */}
            <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                <div className="flex items-center gap-2 text-yellow-400 mb-2">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="font-medium">AI Service Unavailable</span>
                </div>
                <p className="text-sm text-muted-foreground">
                    Showing general explanation. AI-powered insights are temporarily unavailable.
                </p>
            </div>

            {/* Fallback Content */}
            <div className="glass-card rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Info className="w-5 h-5 text-primary" />
                    <h3 className="font-semibold">
                        {category ? `${category} - ${content.title}` : content.title}
                    </h3>
                </div>
                <p className="text-muted-foreground mb-4 leading-relaxed">
                    {content.explanation}
                </p>
            </div>

            {/* Key Insights */}
            <div className="glass-card rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Lightbulb className="w-5 h-5 text-yellow-400" />
                    <h3 className="font-semibold">Key Insights</h3>
                </div>
                <div className="space-y-3">
                    {content.insights.map((insight, index) => (
                        <div
                            key={index}
                            className="flex items-start gap-3 p-3 bg-white/5 rounded-lg"
                        >
                            <div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0" />
                            <p className="text-sm text-muted-foreground">{insight}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}

export default FallbackExplanation
'use client'

import { useState, useCallback } from 'react'
import { api } from '@/lib/api'

export interface ExplanationContext {
    category?: string
    filePath?: string
    branchComparison?: {
        baseBranch: string
        compareBranch: string
    }
    scoreData?: any
}

export interface ExplanationResponse {
    explanation: string
    key_insights: string[]
    recommendations?: string[]
    confidence_level: 'high' | 'medium' | 'low'
    processing_time: number
    fallback_used: boolean
}

export interface AIExplanationState {
    loading: boolean
    data: ExplanationResponse | null
    error: string | null
    isModalOpen: boolean
    explanationType: 'grading' | 'code' | 'comparison' | null
    context: ExplanationContext
}

const FALLBACK_EXPLANATIONS = {
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

export const useAIExplanation = (repoId: string) => {
    const [state, setState] = useState<AIExplanationState>({
        loading: false,
        data: null,
        error: null,
        isModalOpen: false,
        explanationType: null,
        context: {}
    })

    const requestExplanation = useCallback(async (
        type: 'grading' | 'code' | 'comparison',
        context: ExplanationContext
    ) => {
        setState(prev => ({
            ...prev,
            loading: true,
            error: null,
            explanationType: type,
            context,
            isModalOpen: true
        }))

        try {
            const payload = {
                repo_id: repoId,
                explanation_type: type,
                context: context
            }

            const response = await api.post('/explain', payload, {
                timeout: 30000 // 30 second timeout
            })

            setState(prev => ({
                ...prev,
                loading: false,
                data: response.data,
                error: null
            }))
        } catch (error: any) {
            console.error('AI Explanation Error:', error)
            
            // Check if it's a rate limit error
            if (error.response?.status === 429) {
                setState(prev => ({
                    ...prev,
                    loading: false,
                    error: 'Rate limit reached. Please wait a moment before requesting another explanation.',
                }))
            } else if (error.code === 'ECONNABORTED') {
                setState(prev => ({
                    ...prev,
                    loading: false,
                    error: 'Request timed out. The AI service may be busy.',
                }))
            } else {
                // Use fallback explanation
                const fallback = FALLBACK_EXPLANATIONS[type]
                setState(prev => ({
                    ...prev,
                    loading: false,
                    data: {
                        explanation: fallback.explanation,
                        key_insights: fallback.key_insights,
                        confidence_level: 'low' as const,
                        processing_time: 0,
                        fallback_used: true
                    },
                    error: null
                }))
            }
        }
    }, [repoId])

    const explainGrading = useCallback((category?: string, scoreData?: any) => {
        return requestExplanation('grading', { category, scoreData })
    }, [requestExplanation])

    const explainCode = useCallback((filePath: string) => {
        return requestExplanation('code', { filePath })
    }, [requestExplanation])

    const explainComparison = useCallback((baseBranch: string, compareBranch: string) => {
        return requestExplanation('comparison', { 
            branchComparison: { baseBranch, compareBranch } 
        })
    }, [requestExplanation])

    const closeModal = useCallback(() => {
        setState(prev => ({
            ...prev,
            isModalOpen: false,
            data: null,
            error: null,
            explanationType: null,
            context: {}
        }))
    }, [])

    const retry = useCallback(() => {
        if (state.explanationType && state.context) {
            requestExplanation(state.explanationType, state.context)
        }
    }, [state.explanationType, state.context, requestExplanation])

    return {
        ...state,
        explainGrading,
        explainCode,
        explainComparison,
        closeModal,
        retry
    }
}

export default useAIExplanation
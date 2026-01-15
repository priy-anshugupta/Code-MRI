'use client'

import React, { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RefreshCw, AlertTriangle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ErrorFallback } from './ErrorFallback'
import { cn } from '@/lib/utils'

interface RetryWrapperProps {
    children: React.ReactNode
    onRetry: () => Promise<void> | void
    maxRetries?: number
    retryDelay?: number
    exponentialBackoff?: boolean
    showRetryButton?: boolean
    fallbackComponent?: React.ComponentType<any>
    className?: string
}

interface RetryState {
    isRetrying: boolean
    retryCount: number
    lastError: Error | null
    retryDelayRemaining: number
}

export const RetryWrapper: React.FC<RetryWrapperProps> = ({
    children,
    onRetry,
    maxRetries = 3,
    retryDelay = 1000,
    exponentialBackoff = true,
    showRetryButton = true,
    fallbackComponent: FallbackComponent,
    className
}) => {
    const [state, setState] = useState<RetryState>({
        isRetrying: false,
        retryCount: 0,
        lastError: null,
        retryDelayRemaining: 0
    })

    const [retryTimeoutId, setRetryTimeoutId] = useState<NodeJS.Timeout | null>(null)
    const [countdownIntervalId, setCountdownIntervalId] = useState<NodeJS.Timeout | null>(null)

    // Calculate retry delay with exponential backoff
    const getRetryDelay = useCallback((attempt: number) => {
        if (!exponentialBackoff) return retryDelay
        return Math.min(retryDelay * Math.pow(2, attempt), 30000) // Max 30 seconds
    }, [retryDelay, exponentialBackoff])

    // Clean up timers on unmount
    useEffect(() => {
        return () => {
            if (retryTimeoutId) clearTimeout(retryTimeoutId)
            if (countdownIntervalId) clearInterval(countdownIntervalId)
        }
    }, [retryTimeoutId, countdownIntervalId])

    const handleRetry = useCallback(async (isAutoRetry = false) => {
        if (state.isRetrying) return
        
        const newRetryCount = state.retryCount + 1
        
        // Check if we've exceeded max retries
        if (newRetryCount > maxRetries && !isAutoRetry) {
            return
        }

        setState(prev => ({
            ...prev,
            isRetrying: true,
            retryCount: newRetryCount,
            lastError: null
        }))

        try {
            await onRetry()
            
            // Success - reset retry state
            setState({
                isRetrying: false,
                retryCount: 0,
                lastError: null,
                retryDelayRemaining: 0
            })
        } catch (error) {
            const err = error instanceof Error ? error : new Error('Retry failed')
            
            setState(prev => ({
                ...prev,
                isRetrying: false,
                lastError: err
            }))

            // Schedule auto-retry if we haven't exceeded max retries
            if (newRetryCount < maxRetries) {
                const delay = getRetryDelay(newRetryCount - 1)
                
                setState(prev => ({
                    ...prev,
                    retryDelayRemaining: delay
                }))

                // Start countdown
                const interval = setInterval(() => {
                    setState(prev => {
                        const remaining = prev.retryDelayRemaining - 100
                        if (remaining <= 0) {
                            clearInterval(interval)
                            return { ...prev, retryDelayRemaining: 0 }
                        }
                        return { ...prev, retryDelayRemaining: remaining }
                    })
                }, 100)
                setCountdownIntervalId(interval)

                // Schedule retry
                const timeout = setTimeout(() => {
                    handleRetry(true)
                }, delay)
                setRetryTimeoutId(timeout)
            }
        }
    }, [state.isRetrying, state.retryCount, maxRetries, onRetry, getRetryDelay])

    const handleManualRetry = useCallback(() => {
        // Clear any pending auto-retry
        if (retryTimeoutId) {
            clearTimeout(retryTimeoutId)
            setRetryTimeoutId(null)
        }
        if (countdownIntervalId) {
            clearInterval(countdownIntervalId)
            setCountdownIntervalId(null)
        }

        setState(prev => ({
            ...prev,
            retryDelayRemaining: 0
        }))

        handleRetry(false)
    }, [handleRetry, retryTimeoutId, countdownIntervalId])

    const canRetry = state.retryCount < maxRetries
    const isWaitingForRetry = state.retryDelayRemaining > 0

    // If there's an error and we can't retry anymore, show fallback
    if (state.lastError && !canRetry && !state.isRetrying) {
        if (FallbackComponent) {
            return <FallbackComponent error={state.lastError} resetErrorBoundary={handleManualRetry} />
        }

        return (
            <ErrorFallback
                error={state.lastError}
                resetErrorBoundary={handleManualRetry}
                type="generic"
                title="Maximum Retries Exceeded"
                description={`Failed after ${maxRetries} attempts. Please try again later.`}
                showRetry={true}
                retryLabel="Try Again"
                className={className}
            />
        )
    }

    return (
        <div className={cn('relative', className)}>
            {children}
            
            {/* Retry Status Overlay */}
            <AnimatePresence>
                {(state.isRetrying || isWaitingForRetry || (state.lastError && canRetry)) && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg"
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-background border border-white/10 rounded-xl p-6 max-w-sm mx-4 text-center shadow-2xl"
                        >
                            {state.isRetrying && (
                                <>
                                    <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin text-primary" />
                                    <h3 className="font-medium text-foreground mb-2">Retrying...</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Attempt {state.retryCount} of {maxRetries}
                                    </p>
                                </>
                            )}

                            {isWaitingForRetry && (
                                <>
                                    <Clock className="w-8 h-8 mx-auto mb-3 text-yellow-400" />
                                    <h3 className="font-medium text-foreground mb-2">Retrying Soon</h3>
                                    <p className="text-sm text-muted-foreground mb-3">
                                        Next attempt in {Math.ceil(state.retryDelayRemaining / 1000)}s
                                    </p>
                                    {showRetryButton && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleManualRetry}
                                            className="gap-2"
                                        >
                                            <RefreshCw className="w-4 h-4" />
                                            Retry Now
                                        </Button>
                                    )}
                                </>
                            )}

                            {state.lastError && !state.isRetrying && !isWaitingForRetry && canRetry && (
                                <>
                                    <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-red-400" />
                                    <h3 className="font-medium text-foreground mb-2">Operation Failed</h3>
                                    <p className="text-sm text-muted-foreground mb-3">
                                        {state.lastError.message}
                                    </p>
                                    {showRetryButton && (
                                        <div className="flex gap-2 justify-center">
                                            <Button
                                                variant="default"
                                                size="sm"
                                                onClick={handleManualRetry}
                                                className="gap-2"
                                            >
                                                <RefreshCw className="w-4 h-4" />
                                                Retry ({maxRetries - state.retryCount} left)
                                            </Button>
                                        </div>
                                    )}
                                </>
                            )}
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

// Hook for using retry logic in functional components
export const useRetry = (
    operation: () => Promise<void> | void,
    options: {
        maxRetries?: number
        retryDelay?: number
        exponentialBackoff?: boolean
        onError?: (error: Error, retryCount: number) => void
        onSuccess?: () => void
    } = {}
) => {
    const {
        maxRetries = 3,
        retryDelay = 1000,
        exponentialBackoff = true,
        onError,
        onSuccess
    } = options

    const [state, setState] = useState<RetryState>({
        isRetrying: false,
        retryCount: 0,
        lastError: null,
        retryDelayRemaining: 0
    })

    const retry = useCallback(async () => {
        if (state.isRetrying || state.retryCount >= maxRetries) return

        setState(prev => ({
            ...prev,
            isRetrying: true,
            retryCount: prev.retryCount + 1,
            lastError: null
        }))

        try {
            await operation()
            setState({
                isRetrying: false,
                retryCount: 0,
                lastError: null,
                retryDelayRemaining: 0
            })
            onSuccess?.()
        } catch (error) {
            const err = error instanceof Error ? error : new Error('Operation failed')
            setState(prev => ({
                ...prev,
                isRetrying: false,
                lastError: err
            }))
            onError?.(err, state.retryCount + 1)
        }
    }, [operation, state.isRetrying, state.retryCount, maxRetries, onError, onSuccess])

    const reset = useCallback(() => {
        setState({
            isRetrying: false,
            retryCount: 0,
            lastError: null,
            retryDelayRemaining: 0
        })
    }, [])

    return {
        ...state,
        retry,
        reset,
        canRetry: state.retryCount < maxRetries
    }
}

export default RetryWrapper
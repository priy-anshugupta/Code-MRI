'use client'

import { useState, useCallback, useRef } from 'react'

export interface ErrorInfo {
    message: string
    type: 'network' | 'api' | 'timeout' | 'validation' | 'auth' | 'generic'
    code?: string | number
    details?: any
    timestamp: Date
    retryable: boolean
}

export interface ErrorHandlerOptions {
    defaultRetryable?: boolean
    logErrors?: boolean
    reportErrors?: boolean
    maxRetries?: number
    retryDelay?: number
}

export interface ErrorHandlerState {
    error: ErrorInfo | null
    isRetrying: boolean
    retryCount: number
    hasError: boolean
}

const defaultOptions: ErrorHandlerOptions = {
    defaultRetryable: true,
    logErrors: true,
    reportErrors: false,
    maxRetries: 3,
    retryDelay: 1000
}

export const useErrorHandler = (options: ErrorHandlerOptions = {}) => {
    const opts = { ...defaultOptions, ...options }
    const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    
    const [state, setState] = useState<ErrorHandlerState>({
        error: null,
        isRetrying: false,
        retryCount: 0,
        hasError: false
    })

    // Parse error to determine type and retryability
    const parseError = useCallback((error: any): ErrorInfo => {
        let type: ErrorInfo['type'] = 'generic'
        let retryable = opts.defaultRetryable
        let message = 'An unexpected error occurred'
        let code: string | number | undefined
        let details: any

        if (error instanceof Error) {
            message = error.message
            details = error.stack
        } else if (typeof error === 'string') {
            message = error
        } else if (error?.response) {
            // Axios-style error
            const status = error.response.status
            message = error.response.data?.detail || error.response.data?.message || error.message
            code = status
            details = error.response.data

            if (status >= 500) {
                type = 'api'
                retryable = true
            } else if (status === 401 || status === 403) {
                type = 'auth'
                retryable = false
            } else if (status === 408 || status === 504) {
                type = 'timeout'
                retryable = true
            } else if (status >= 400) {
                type = 'validation'
                retryable = false
            }
        } else if (error?.code === 'ECONNABORTED' || error?.code === 'NETWORK_ERROR') {
            type = 'network'
            retryable = true
            message = 'Network connection failed'
        } else if (error?.code === 'TIMEOUT') {
            type = 'timeout'
            retryable = true
            message = 'Request timed out'
        }

        return {
            message,
            type,
            code,
            details,
            timestamp: new Date(),
            retryable: retryable ?? (opts.defaultRetryable ?? true)
        }
    }, [opts.defaultRetryable])

    // Handle error
    const handleError = useCallback((error: any) => {
        const errorInfo = parseError(error)
        
        setState(prev => ({
            ...prev,
            error: errorInfo,
            hasError: true,
            isRetrying: false
        }))

        // Log error if enabled
        if (opts.logErrors) {
            console.error('Error handled:', errorInfo)
        }

        // Report error if enabled (you could integrate with error reporting services here)
        if (opts.reportErrors) {
            // Example: reportToSentry(errorInfo)
            console.info('Error reported:', errorInfo)
        }

        return errorInfo
    }, [parseError, opts.logErrors, opts.reportErrors])

    // Clear error
    const clearError = useCallback(() => {
        if (retryTimeoutRef.current) {
            clearTimeout(retryTimeoutRef.current)
            retryTimeoutRef.current = null
        }

        setState({
            error: null,
            isRetrying: false,
            retryCount: 0,
            hasError: false
        })
    }, [])

    // Retry operation
    const retry = useCallback(async (operation: () => Promise<any> | any) => {
        if (!state.error?.retryable || state.retryCount >= opts.maxRetries!) {
            return Promise.reject(state.error)
        }

        setState(prev => ({
            ...prev,
            isRetrying: true,
            retryCount: prev.retryCount + 1
        }))

        try {
            const result = await operation()
            clearError()
            return result
        } catch (error) {
            const errorInfo = handleError(error)
            
            // Schedule auto-retry if still retryable
            if (errorInfo.retryable && state.retryCount + 1 < opts.maxRetries!) {
                retryTimeoutRef.current = setTimeout(() => {
                    retry(operation)
                }, opts.retryDelay! * Math.pow(2, state.retryCount)) // Exponential backoff
            }
            
            throw errorInfo
        }
    }, [state.error, state.retryCount, opts.maxRetries, opts.retryDelay, clearError, handleError])

    // Execute operation with error handling
    const execute = useCallback(async (operation: () => Promise<any> | any) => {
        clearError()
        
        try {
            return await operation()
        } catch (error) {
            throw handleError(error)
        }
    }, [clearError, handleError])

    // Execute with automatic retry
    const executeWithRetry = useCallback(async (operation: () => Promise<any> | any) => {
        clearError()
        
        try {
            return await operation()
        } catch (error) {
            handleError(error)
            return retry(operation)
        }
    }, [clearError, handleError, retry])

    // Get user-friendly error message
    const getErrorMessage = useCallback((error?: ErrorInfo) => {
        const err = error || state.error
        if (!err) return null

        switch (err.type) {
            case 'network':
                return 'Please check your internet connection and try again.'
            case 'api':
                return 'Server error occurred. Please try again in a moment.'
            case 'timeout':
                return 'Request timed out. Please try again.'
            case 'auth':
                return 'Authentication required. Please log in and try again.'
            case 'validation':
                return err.message || 'Invalid input. Please check your data and try again.'
            default:
                return err.message || 'An unexpected error occurred.'
        }
    }, [state.error])

    // Check if error is recoverable
    const isRecoverable = useCallback((error?: ErrorInfo) => {
        const err = error || state.error
        return err?.retryable && state.retryCount < opts.maxRetries!
    }, [state.error, state.retryCount, opts.maxRetries])

    return {
        // State
        error: state.error,
        hasError: state.hasError,
        isRetrying: state.isRetrying,
        retryCount: state.retryCount,
        canRetry: isRecoverable(),

        // Actions
        handleError,
        clearError,
        retry,
        execute,
        executeWithRetry,

        // Utilities
        getErrorMessage,
        isRecoverable,
        
        // Error type checks
        isNetworkError: state.error?.type === 'network',
        isAPIError: state.error?.type === 'api',
        isTimeoutError: state.error?.type === 'timeout',
        isAuthError: state.error?.type === 'auth',
        isValidationError: state.error?.type === 'validation'
    }
}

// Specialized hooks for common scenarios
export const useAPIErrorHandler = (options?: Omit<ErrorHandlerOptions, 'defaultRetryable'>) => {
    return useErrorHandler({ ...options, defaultRetryable: true })
}

export const useNetworkErrorHandler = (options?: Omit<ErrorHandlerOptions, 'defaultRetryable'>) => {
    return useErrorHandler({ ...options, defaultRetryable: true })
}

export const useValidationErrorHandler = (options?: Omit<ErrorHandlerOptions, 'defaultRetryable'>) => {
    return useErrorHandler({ ...options, defaultRetryable: false })
}

export default useErrorHandler
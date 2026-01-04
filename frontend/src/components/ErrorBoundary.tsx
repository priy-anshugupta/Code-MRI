'use client'

import React, { Component, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Home, Bug, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { motion, AnimatePresence } from 'framer-motion'

interface ErrorBoundaryState {
    hasError: boolean
    error: Error | null
    errorInfo: React.ErrorInfo | null
    showDetails: boolean
    retryCount: number
}

interface ErrorBoundaryProps {
    children: ReactNode
    fallback?: ReactNode
    onError?: (error: Error, errorInfo: React.ErrorInfo) => void
    resetOnPropsChange?: boolean
    resetKeys?: Array<string | number>
    level?: 'page' | 'component' | 'section'
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    private resetTimeoutId: number | null = null

    constructor(props: ErrorBoundaryProps) {
        super(props)
        this.state = {
            hasError: false,
            error: null,
            errorInfo: null,
            showDetails: false,
            retryCount: 0
        }
    }

    static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
        return {
            hasError: true,
            error
        }
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo)
        
        this.setState({
            error,
            errorInfo
        })

        // Call custom error handler if provided
        if (this.props.onError) {
            this.props.onError(error, errorInfo)
        }

        // Report error to monitoring service (if available)
        this.reportError(error, errorInfo)
    }

    componentDidUpdate(prevProps: ErrorBoundaryProps) {
        const { resetKeys, resetOnPropsChange } = this.props
        const { hasError } = this.state

        if (hasError && prevProps.resetKeys !== resetKeys) {
            if (resetKeys?.some((key, idx) => prevProps.resetKeys?.[idx] !== key)) {
                this.resetErrorBoundary()
            }
        }

        if (hasError && resetOnPropsChange && prevProps.children !== this.props.children) {
            this.resetErrorBoundary()
        }
    }

    componentWillUnmount() {
        if (this.resetTimeoutId) {
            window.clearTimeout(this.resetTimeoutId)
        }
    }

    private reportError = (error: Error, errorInfo: React.ErrorInfo) => {
        // In a real application, you would send this to your error reporting service
        // For now, we'll just log it with additional context
        const errorReport = {
            message: error.message,
            stack: error.stack,
            componentStack: errorInfo.componentStack,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href,
            level: this.props.level || 'component'
        }

        console.error('Error Report:', errorReport)
        
        // You could send this to services like Sentry, LogRocket, etc.
        // Example: Sentry.captureException(error, { contexts: { react: errorInfo } })
    }

    private resetErrorBoundary = () => {
        if (this.resetTimeoutId) {
            window.clearTimeout(this.resetTimeoutId)
        }

        this.setState({
            hasError: false,
            error: null,
            errorInfo: null,
            showDetails: false,
            retryCount: this.state.retryCount + 1
        })
    }

    private handleRetry = () => {
        this.resetErrorBoundary()
    }

    private handleRetryWithDelay = () => {
        this.setState({ retryCount: this.state.retryCount + 1 })
        
        this.resetTimeoutId = window.setTimeout(() => {
            this.resetErrorBoundary()
        }, 1000)
    }

    private toggleDetails = () => {
        this.setState({ showDetails: !this.state.showDetails })
    }

    private getErrorLevel = () => {
        return this.props.level || 'component'
    }

    private getErrorTitle = () => {
        const level = this.getErrorLevel()
        switch (level) {
            case 'page':
                return 'Page Error'
            case 'section':
                return 'Section Error'
            default:
                return 'Component Error'
        }
    }

    private getErrorDescription = () => {
        const level = this.getErrorLevel()
        switch (level) {
            case 'page':
                return 'An error occurred while loading this page. The application is still functional.'
            case 'section':
                return 'An error occurred in this section. Other parts of the page should still work.'
            default:
                return 'An error occurred in this component. You can try refreshing or continue using other features.'
        }
    }

    private getRecoveryOptions = () => {
        const level = this.getErrorLevel()
        const { retryCount } = this.state

        const options = [
            {
                label: retryCount > 0 ? `Retry (${retryCount + 1})` : 'Retry',
                action: this.handleRetry,
                icon: RefreshCw,
                primary: true
            }
        ]

        if (level === 'page') {
            options.push({
                label: 'Go Home',
                action: () => window.location.href = '/',
                icon: Home,
                primary: false
            })
        }

        if (retryCount > 2) {
            options.push({
                label: 'Retry with Delay',
                action: this.handleRetryWithDelay,
                icon: RefreshCw,
                primary: false
            })
        }

        return options
    }

    render() {
        if (this.state.hasError) {
            // Use custom fallback if provided
            if (this.props.fallback) {
                return this.props.fallback
            }

            const { error, errorInfo, showDetails } = this.state
            const level = this.getErrorLevel()
            const recoveryOptions = this.getRecoveryOptions()

            return (
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className={`
                        flex flex-col items-center justify-center p-6 rounded-xl border
                        ${level === 'page' 
                            ? 'min-h-[50vh] bg-red-500/5 border-red-500/20' 
                            : 'min-h-[200px] bg-red-500/5 border-red-500/20'
                        }
                    `}
                >
                    <div className="text-center max-w-md">
                        {/* Error Icon */}
                        <div className="mb-4">
                            <AlertTriangle className="w-16 h-16 mx-auto text-red-400" />
                        </div>

                        {/* Error Title */}
                        <h2 className="text-xl font-semibold text-foreground mb-2">
                            {this.getErrorTitle()}
                        </h2>

                        {/* Error Description */}
                        <p className="text-muted-foreground mb-4 text-sm leading-relaxed">
                            {this.getErrorDescription()}
                        </p>

                        {/* Error Message */}
                        {error && (
                            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                                <p className="text-red-400 text-sm font-mono">
                                    {error.message}
                                </p>
                            </div>
                        )}

                        {/* Recovery Actions */}
                        <div className="flex flex-wrap gap-2 justify-center mb-4">
                            {recoveryOptions.map((option, index) => (
                                <Button
                                    key={index}
                                    variant={option.primary ? "default" : "outline"}
                                    size="sm"
                                    onClick={option.action}
                                    className="gap-2"
                                >
                                    <option.icon className="w-4 h-4" />
                                    {option.label}
                                </Button>
                            ))}
                        </div>

                        {/* Error Details Toggle */}
                        {(error || errorInfo) && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={this.toggleDetails}
                                className="gap-2 text-muted-foreground"
                            >
                                <Bug className="w-4 h-4" />
                                {showDetails ? 'Hide' : 'Show'} Details
                                {showDetails ? (
                                    <ChevronUp className="w-4 h-4" />
                                ) : (
                                    <ChevronDown className="w-4 h-4" />
                                )}
                            </Button>
                        )}

                        {/* Error Details */}
                        <AnimatePresence>
                            {showDetails && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    className="mt-4 text-left"
                                >
                                    <div className="bg-black/50 border border-white/10 rounded-lg p-4 max-h-64 overflow-y-auto">
                                        {error && (
                                            <div className="mb-4">
                                                <h4 className="text-sm font-medium text-red-400 mb-2">Error Stack:</h4>
                                                <pre className="text-xs text-muted-foreground font-mono whitespace-pre-wrap">
                                                    {error.stack}
                                                </pre>
                                            </div>
                                        )}
                                        {errorInfo && (
                                            <div>
                                                <h4 className="text-sm font-medium text-red-400 mb-2">Component Stack:</h4>
                                                <pre className="text-xs text-muted-foreground font-mono whitespace-pre-wrap">
                                                    {errorInfo.componentStack}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </motion.div>
            )
        }

        return this.props.children
    }
}

// Higher-order component for easier usage
export function withErrorBoundary<P extends object>(
    Component: React.ComponentType<P>,
    errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
    const WrappedComponent = (props: P) => (
        <ErrorBoundary {...errorBoundaryProps}>
            <Component {...props} />
        </ErrorBoundary>
    )

    WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`
    return WrappedComponent
}

export default ErrorBoundary
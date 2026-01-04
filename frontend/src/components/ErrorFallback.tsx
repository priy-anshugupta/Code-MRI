'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { 
    AlertTriangle, 
    RefreshCw, 
    Home, 
    Wifi, 
    Server, 
    Clock,
    FileX,
    GitBranch,
    Brain,
    Shield,
    Loader2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface ErrorFallbackProps {
    error?: Error
    resetErrorBoundary?: () => void
    type?: 'network' | 'api' | 'timeout' | 'file' | 'branch' | 'ai' | 'auth' | 'generic'
    title?: string
    description?: string
    showRetry?: boolean
    showHome?: boolean
    retryLabel?: string
    className?: string
    size?: 'sm' | 'md' | 'lg'
}

const errorTypeConfig = {
    network: {
        icon: Wifi,
        title: 'Network Connection Error',
        description: 'Unable to connect to the server. Please check your internet connection.',
        color: 'text-orange-400',
        bgColor: 'bg-orange-500/10',
        borderColor: 'border-orange-500/20'
    },
    api: {
        icon: Server,
        title: 'API Error',
        description: 'The server encountered an error while processing your request.',
        color: 'text-red-400',
        bgColor: 'bg-red-500/10',
        borderColor: 'border-red-500/20'
    },
    timeout: {
        icon: Clock,
        title: 'Request Timeout',
        description: 'The request took too long to complete. The server might be busy.',
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-500/10',
        borderColor: 'border-yellow-500/20'
    },
    file: {
        icon: FileX,
        title: 'File Error',
        description: 'Unable to load or process the requested file.',
        color: 'text-purple-400',
        bgColor: 'bg-purple-500/10',
        borderColor: 'border-purple-500/20'
    },
    branch: {
        icon: GitBranch,
        title: 'Branch Error',
        description: 'Unable to switch branches or load branch data.',
        color: 'text-blue-400',
        bgColor: 'bg-blue-500/10',
        borderColor: 'border-blue-500/20'
    },
    ai: {
        icon: Brain,
        title: 'AI Service Error',
        description: 'The AI explanation service is currently unavailable.',
        color: 'text-cyan-400',
        bgColor: 'bg-cyan-500/10',
        borderColor: 'border-cyan-500/20'
    },
    auth: {
        icon: Shield,
        title: 'Authentication Error',
        description: 'You need to authenticate to access this resource.',
        color: 'text-red-400',
        bgColor: 'bg-red-500/10',
        borderColor: 'border-red-500/20'
    },
    generic: {
        icon: AlertTriangle,
        title: 'Something went wrong',
        description: 'An unexpected error occurred. Please try again.',
        color: 'text-red-400',
        bgColor: 'bg-red-500/10',
        borderColor: 'border-red-500/20'
    }
}

const sizeConfig = {
    sm: {
        container: 'p-4 min-h-[120px]',
        icon: 'w-8 h-8',
        title: 'text-sm font-medium',
        description: 'text-xs',
        button: 'text-xs'
    },
    md: {
        container: 'p-6 min-h-[200px]',
        icon: 'w-12 h-12',
        title: 'text-lg font-semibold',
        description: 'text-sm',
        button: 'text-sm'
    },
    lg: {
        container: 'p-8 min-h-[300px]',
        icon: 'w-16 h-16',
        title: 'text-xl font-semibold',
        description: 'text-base',
        button: 'text-base'
    }
}

export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
    error,
    resetErrorBoundary,
    type = 'generic',
    title,
    description,
    showRetry = true,
    showHome = false,
    retryLabel = 'Try Again',
    className,
    size = 'md'
}) => {
    const config = errorTypeConfig[type]
    const sizeStyles = sizeConfig[size]
    const Icon = config.icon

    const handleRetry = () => {
        if (resetErrorBoundary) {
            resetErrorBoundary()
        } else {
            window.location.reload()
        }
    }

    const handleGoHome = () => {
        window.location.href = '/'
    }

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn(
                'flex flex-col items-center justify-center rounded-xl border',
                config.bgColor,
                config.borderColor,
                sizeStyles.container,
                className
            )}
        >
            <div className="text-center max-w-md">
                {/* Error Icon */}
                <div className="mb-4">
                    <Icon className={cn(sizeStyles.icon, 'mx-auto', config.color)} />
                </div>

                {/* Error Title */}
                <h3 className={cn(sizeStyles.title, 'text-foreground mb-2')}>
                    {title || config.title}
                </h3>

                {/* Error Description */}
                <p className={cn(sizeStyles.description, 'text-muted-foreground mb-4 leading-relaxed')}>
                    {description || config.description}
                </p>

                {/* Error Message */}
                {error && (
                    <div className="mb-4 p-3 bg-black/30 border border-white/10 rounded-lg">
                        <p className={cn(sizeStyles.description, 'text-red-400 font-mono')}>
                            {error.message}
                        </p>
                    </div>
                )}

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-2 justify-center">
                    {showRetry && (
                        <Button
                            variant="default"
                            size={size === 'sm' ? 'sm' : 'default'}
                            onClick={handleRetry}
                            className="gap-2"
                        >
                            <RefreshCw className="w-4 h-4" />
                            {retryLabel}
                        </Button>
                    )}
                    
                    {showHome && (
                        <Button
                            variant="outline"
                            size={size === 'sm' ? 'sm' : 'default'}
                            onClick={handleGoHome}
                            className="gap-2"
                        >
                            <Home className="w-4 h-4" />
                            Go Home
                        </Button>
                    )}
                </div>
            </div>
        </motion.div>
    )
}

// Loading fallback component for suspense boundaries
export const LoadingFallback: React.FC<{
    message?: string
    size?: 'sm' | 'md' | 'lg'
    className?: string
}> = ({ 
    message = 'Loading...', 
    size = 'md',
    className 
}) => {
    const sizeStyles = sizeConfig[size]

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className={cn(
                'flex flex-col items-center justify-center',
                sizeStyles.container,
                className
            )}
        >
            <Loader2 className={cn(sizeStyles.icon, 'animate-spin text-primary mb-4')} />
            <p className={cn(sizeStyles.description, 'text-muted-foreground animate-pulse')}>
                {message}
            </p>
        </motion.div>
    )
}

// Specific error fallback components for common scenarios
export const NetworkErrorFallback: React.FC<Omit<ErrorFallbackProps, 'type'>> = (props) => (
    <ErrorFallback {...props} type="network" />
)

export const APIErrorFallback: React.FC<Omit<ErrorFallbackProps, 'type'>> = (props) => (
    <ErrorFallback {...props} type="api" />
)

export const TimeoutErrorFallback: React.FC<Omit<ErrorFallbackProps, 'type'>> = (props) => (
    <ErrorFallback {...props} type="timeout" />
)

export const FileErrorFallback: React.FC<Omit<ErrorFallbackProps, 'type'>> = (props) => (
    <ErrorFallback {...props} type="file" />
)

export const BranchErrorFallback: React.FC<Omit<ErrorFallbackProps, 'type'>> = (props) => (
    <ErrorFallback {...props} type="branch" />
)

export const AIErrorFallback: React.FC<Omit<ErrorFallbackProps, 'type'>> = (props) => (
    <ErrorFallback {...props} type="ai" />
)

export const AuthErrorFallback: React.FC<Omit<ErrorFallbackProps, 'type'>> = (props) => (
    <ErrorFallback {...props} type="auth" />
)

export default ErrorFallback
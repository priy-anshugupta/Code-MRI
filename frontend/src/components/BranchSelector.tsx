'use client'

import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { GitBranch, ChevronDown, Loader2, Check, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useErrorHandler } from '@/hooks/useErrorHandler'
import { ErrorFallback } from './ErrorFallback'

interface BranchInfo {
    name: string
    commit_sha: string
    is_default: boolean
    last_commit_date: string
    last_analyzed: string | null
}

interface BranchSelectorProps {
    repoId: string
    currentBranch?: string
    branches?: BranchInfo[]  // Optional: if provided, won't fetch
    onBranchChange?: (branch: string, branchInfo: BranchInfo) => void
    className?: string
}

export const BranchSelector: React.FC<BranchSelectorProps> = ({
    repoId,
    currentBranch,
    branches: branchesProp,
    onBranchChange,
    className
}) => {
    const [branches, setBranches] = useState<BranchInfo[]>(branchesProp || [])
    const [selectedBranch, setSelectedBranch] = useState<string>(currentBranch || '')
    const [isOpen, setIsOpen] = useState(false)
    const [loading, setLoading] = useState(false)
    const [switching, setSwitching] = useState(false)
    const dropdownRef = useRef<HTMLDivElement>(null)
    
    const errorHandler = useErrorHandler({
        maxRetries: 2,
        retryDelay: 1500
    })

    // Update branches when prop changes
    useEffect(() => {
        if (branchesProp && branchesProp.length > 0) {
            setBranches(branchesProp)
        }
    }, [branchesProp])

    // Fetch branches on component mount only if not provided
    useEffect(() => {
        if (!branchesProp && branches.length === 0) {
            fetchBranches()
        }
    }, [repoId, branchesProp]) // eslint-disable-line react-hooks/exhaustive-deps

    // Sync selectedBranch with currentBranch prop
    useEffect(() => {
        if (currentBranch && currentBranch !== selectedBranch) {
            setSelectedBranch(currentBranch)
        }
    }, [currentBranch])

    // Handle click outside to close dropdown
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const fetchBranches = async () => {
        setLoading(true)
        errorHandler.clearError()
        
        try {
            const response = await errorHandler.execute(() => api.get(`/branches/${repoId}`))
            const branchData = response.data.branches as BranchInfo[]
            setBranches(branchData)
            
            // Set default branch if no current branch is specified
            if (!currentBranch && branchData.length > 0) {
                const defaultBranch = branchData.find(b => b.is_default) || branchData[0]
                setSelectedBranch(defaultBranch.name)
            }
        } catch (error) {
            console.error('BranchSelector fetch error:', error)
            // Error is handled by errorHandler
        } finally {
            setLoading(false)
        }
    }

    const handleBranchSelect = async (branch: BranchInfo) => {
        if (branch.name === selectedBranch) {
            setIsOpen(false)
            return
        }

        setSwitching(true)
        errorHandler.clearError()

        try {
            const response = await errorHandler.execute(() => 
                api.post('/switch-branch', {
                    repo_id: repoId,
                    branch: branch.name
                })
            )

            setSelectedBranch(branch.name)
            setIsOpen(false)
            
            // Notify parent component of branch change
            if (onBranchChange) {
                onBranchChange(branch.name, branch)
            }
        } catch (error) {
            // Error is handled by errorHandler
        } finally {
            setSwitching(false)
        }
    }

    const selectedBranchInfo = branches.find(b => b.name === selectedBranch)
    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        })
    }

    if (loading && branches.length === 0) {
        return (
            <div className={cn("flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10", className)}>
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Loading branches...</span>
            </div>
        )
    }

    // Show error fallback if there's an error and no branches loaded
    if (errorHandler.hasError && branches.length === 0) {
        return (
            <div className={className}>
                <ErrorFallback
                    error={errorHandler.error ? new Error(errorHandler.getErrorMessage() || 'Unknown error') : undefined}
                    type={errorHandler.isNetworkError ? 'network' : 
                          errorHandler.isAPIError ? 'api' : 'branch'}
                    resetErrorBoundary={() => errorHandler.executeWithRetry(fetchBranches)}
                    showRetry={errorHandler.canRetry}
                    size="sm"
                    title="Failed to Load Branches"
                />
            </div>
        )
    }

    return (
        <div className={cn("relative", className)} ref={dropdownRef}>
            {/* Branch Selector Button */}
            <Button
                variant="outline"
                onClick={() => setIsOpen(!isOpen)}
                disabled={switching || branches.length === 0}
                className="flex items-center gap-2 min-w-[200px] justify-between"
            >
                <div className="flex items-center gap-2">
                    <GitBranch className="h-4 w-4 text-primary" />
                    <span className="font-mono text-sm">
                        {switching ? 'Switching...' : selectedBranch || 'Select branch'}
                    </span>
                    {selectedBranchInfo?.is_default && (
                        <span className="text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded border border-primary/30">
                            DEFAULT
                        </span>
                    )}
                </div>
                {switching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                    <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
                )}
            </Button>

            {/* Error Display */}
            {errorHandler.hasError && branches.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-2">
                    <ErrorFallback
                        error={errorHandler.error ? new Error(errorHandler.getErrorMessage() || 'Unknown error') : undefined}
                        type={errorHandler.isNetworkError ? 'network' : 
                              errorHandler.isAPIError ? 'api' : 'branch'}
                        resetErrorBoundary={() => errorHandler.executeWithRetry(() => handleBranchSelect(branches.find(b => b.name === selectedBranch)!))}
                        showRetry={errorHandler.canRetry}
                        size="sm"
                        className="backdrop-blur-md"
                    />
                </div>
            )}

            {/* Dropdown Menu */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -10, scale: 0.95 }}
                        transition={{ duration: 0.2 }}
                        className="absolute top-full left-0 right-0 mt-2 bg-black/90 backdrop-blur-xl border border-white/10 rounded-lg shadow-2xl z-50 max-h-64 overflow-y-auto custom-scrollbar"
                    >
                        {branches.length === 0 ? (
                            <div className="p-4 text-center text-muted-foreground text-sm">No branches found</div>
                        ) : (
                            <div className="p-2">
                                {branches.map((branch) => (
                                    <motion.button
                                        key={branch.name}
                                        onClick={() => handleBranchSelect(branch)}
                                        className={cn(
                                            "w-full flex items-center justify-between p-3 rounded-lg text-left transition-all duration-200 group",
                                            branch.name === selectedBranch
                                                ? "bg-primary/10 text-primary border border-primary/20"
                                                : "hover:bg-white/5 text-foreground"
                                        )}
                                        whileHover={{ scale: 1.02 }}
                                        whileTap={{ scale: 0.98 }}
                                    >
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <GitBranch className="h-3 w-3 flex-shrink-0" />
                                                <span className="font-mono text-sm font-medium truncate">
                                                    {branch.name}
                                                </span>
                                                {branch.is_default && (
                                                    <span className="text-xs bg-primary/20 text-primary px-1.5 py-0.5 rounded border border-primary/30 flex-shrink-0">
                                                        DEFAULT
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                                <span className="font-mono">{branch.commit_sha.substring(0, 7)}</span>
                                                <span>{formatDate(branch.last_commit_date)}</span>
                                                {branch.last_analyzed && (
                                                    <span className="text-green-400">✓ Analyzed</span>
                                                )}
                                            </div>
                                        </div>
                                        {branch.name === selectedBranch && (
                                            <Check className="h-4 w-4 text-primary flex-shrink-0" />
                                        )}
                                    </motion.button>
                                ))}
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
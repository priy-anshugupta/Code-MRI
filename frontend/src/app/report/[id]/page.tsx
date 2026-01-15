'use client'

import { useCallback, useEffect, useState, useRef } from 'react'
import { FileTree } from '@/components/FileTree'
import { CodeViewModal } from '@/components/CodeViewModal'
import { BranchSelector } from '@/components/BranchSelector'
import { BranchComparisonModal } from '@/components/BranchComparisonModal'
import { ScoreBreakdown } from '@/components/ScoreBreakdown'
import { AIExplanationModal } from '@/components/AIExplanationModal'
import { HistoricalTrendsPanel } from '@/components/HistoricalTrendsPanel'
import ErrorBoundary from '@/components/ErrorBoundary'
import { ErrorFallback } from '@/components/ErrorFallback'
import { useErrorHandler } from '@/hooks/useErrorHandler'
import { GitBranch, ShieldCheck, Cpu, AlertTriangle, Terminal, FileCode, Loader2, X, Eye, Activity, Layers, Box, CheckCircle2, GitCompare, Brain, TrendingUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { useAIExplanation } from '@/hooks/useAIExplanation'

// Right Sidebar Component - AI Assistant Only
const AIAssistant = ({ repoId }: { repoId: string }) => {
    const [messages, setMessages] = useState<{ role: 'system' | 'user' | 'bot', text: string }[]>([
        { role: 'system', text: 'System ready. Repository analysis complete. Waiting for query...' }
    ])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!input.trim()) return

        const userMsg = input
        setMessages(p => [...p, { role: 'user', text: userMsg }])
        setInput('')
        setLoading(true)

        try {
            const res = await api.post('/chat', {
                repo_id: repoId,
                message: userMsg
            })
            setMessages(p => [...p, { role: 'bot', text: res.data.response }])
        } catch (err) {
            setMessages(p => [...p, { role: 'bot', text: 'Error: Could not retrieve answer.' }])
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="h-full flex flex-col">
            <div className="p-4 border-b border-white/10 bg-white/5">
                <h3 className="font-semibold text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                    AI ASSISTANT
                </h3>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
                {messages.map((m, i) => (
                    <div key={i} className={`text-sm ${m.role === 'system' ? 'font-mono text-xs' : ''}`}>
                        {m.role === 'system' && (
                            <div className="text-green-400/80 bg-green-500/5 p-3 rounded border border-green-500/20">
                                <span className="text-green-500 mr-2">@ SYSTEM</span>
                                {m.text}
                            </div>
                        )}
                        {m.role === 'user' && (
                            <div className="bg-primary/20 text-primary-foreground p-3 rounded ml-4">
                                {m.text}
                            </div>
                        )}
                        {m.role === 'bot' && (
                            <div className="bg-white/5 p-3 rounded border border-white/5">
                                <MarkdownRenderer content={String(m.text || '')} />
                            </div>
                        )}
                    </div>
                ))}
                {loading && <div className="text-xs text-muted-foreground animate-pulse font-mono">Processing query...</div>}
            </div>
            <form onSubmit={handleSend} className="p-4 border-t border-white/10 bg-white/5">
                <div className="flex gap-2 items-center">
                    <span className="text-primary">{'>'}</span>
                    <input
                        className="flex-1 bg-transparent border-none text-sm focus:outline-none placeholder:text-muted-foreground"
                        placeholder="Execute query..."
                        value={input}
                        onChange={e => setInput(e.target.value)}
                    />
                </div>
            </form>
        </div>
    )
}

// Types (kept same as before)
interface FileMetrics {
    loc?: number
    comments?: number
    complexity?: number
}

interface FileNode {
    name: string
    type: 'file' | 'folder'
    children?: FileNode[]
    metrics?: FileMetrics
}

interface Issue {
    severity: 'HIGH' | 'MEDIUM' | 'LOW'
    title: string
    file: string
    line: number
    type: string
    function?: string
}

interface Metrics {
    readability: number
    complexity: number
    maintainability: number
    docs_coverage: number
    grade: string
    total_files: number
    total_loc: number
}

interface ScoringData {
    category_scores: {
        readability: number
        complexity: number
        docs_coverage: number
        security: number
    }
    final_score: number
    ai_analysis: string
    file_count: number
    total_loc: number
}

interface ReportData {
    repo_id: string
    tree: FileNode
    technologies: string[]
    metrics: Metrics
    issues: Issue[]
    summary: string
    scoring?: ScoringData
}

interface FileAnalysis {
    file: string
    metrics?: FileMetrics
    summary?: string
    purpose?: string
    key_elements?: Array<{ name: string; description: string } | string>
    patterns?: string
    quality_notes?: string
    error?: string
    truncated?: boolean
}

// Components
const StatCard = ({ label, value, icon: Icon, trend }: { label: string, value: string | number, icon: any, trend?: string }) => (
    <div className="glass-card p-6 rounded-xl relative overflow-hidden group hover:border-primary/30 transition-all duration-300">
        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Icon className="w-16 h-16" />
        </div>
        <div className="relative z-10">
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
                <Icon className="w-4 h-4" />
                <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
            </div>
            <div className="text-3xl font-bold text-foreground tracking-tight">{value}</div>
            {trend && <div className="text-xs text-green-400 mt-1">{trend}</div>}
        </div>
    </div>
)

const GradeCircle = ({ grade }: { grade: string }) => {
    const color = grade.startsWith('A') ? 'text-green-400 border-green-500/50 shadow-[0_0_30px_rgba(74,222,128,0.2)]' :
                  grade.startsWith('B') ? 'text-blue-400 border-blue-500/50 shadow-[0_0_30px_rgba(96,165,250,0.2)]' :
                  grade.startsWith('C') ? 'text-yellow-400 border-yellow-500/50 shadow-[0_0_30px_rgba(250,204,21,0.2)]' :
                  'text-red-400 border-red-500/50 shadow-[0_0_30px_rgba(248,113,113,0.2)]'
    
    return (
        <div className={cn("w-32 h-32 rounded-full border-4 flex items-center justify-center bg-background/50 backdrop-blur-sm", color)}>
            <div className="text-center">
                <div className="text-5xl font-bold">{grade}</div>
                <div className="text-xs font-medium opacity-70 mt-1">OVERALL</div>
            </div>
        </div>
    )
}

const IssueCard = ({ issue }: { issue: Issue }) => (
    <div className="group p-4 rounded-lg bg-white/5 border border-white/5 hover:border-primary/20 hover:bg-white/10 transition-all duration-200">
        <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                    <span className={cn(
                        "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border",
                        issue.severity === 'HIGH' ? "bg-red-500/10 text-red-400 border-red-500/20" :
                        issue.severity === 'MEDIUM' ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" :
                        "bg-blue-500/10 text-blue-400 border-blue-500/20"
                    )}>
                        {issue.severity}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">{issue.type}</span>
                </div>
                <h4 className="text-sm font-medium text-foreground/90 mb-1">{issue.title}</h4>
                <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
                    <FileCode className="w-3 h-3" />
                    {issue.file}:{issue.line}
                </div>
            </div>
        </div>
    </div>
)

export default function ReportPage({ params }: { params: { id: string } }) {
    const [data, setData] = useState<ReportData | null>(null)
    const [loading, setLoading] = useState(true)
    const [selectedFile, setSelectedFile] = useState<string | null>(null)
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [fileAnalysis, setFileAnalysis] = useState<FileAnalysis | null>(null)
    const [analyzingFile, setAnalyzingFile] = useState(false)
    const [fileTreeWidth, setFileTreeWidth] = useState(288)
    const [assistantWidth, setAssistantWidth] = useState(360)
    const [currentBranch, setCurrentBranch] = useState<string>('')
    const [branches, setBranches] = useState<any[]>([])
    const [isComparisonModalOpen, setIsComparisonModalOpen] = useState(false)
    const [comparisonBranch, setComparisonBranch] = useState<string>('')
    const resizeRef = useRef({ dragging: null as null | 'left' | 'right', startX: 0, startLeftWidth: 288, startRightWidth: 360 })
    
    // AI Explanation integration
    const aiExplanation = useAIExplanation(params.id)
    
    // Error handling
    const errorHandler = useErrorHandler({
        maxRetries: 2,
        retryDelay: 2000
    })

    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await errorHandler.execute(() => api.get(`/report/${params.id}`))
                setData(res.data)
                
                // Fetch branches for the repository
                try {
                    const branchRes = await api.get(`/branches/${params.id}`)
                    setBranches(branchRes.data.branches)
                    
                    // Set current branch to default branch if available
                    const defaultBranch = branchRes.data.branches.find((b: any) => b.is_default)
                    if (defaultBranch) {
                        setCurrentBranch(defaultBranch.name)
                    }
                } catch (branchErr) {
                    console.warn('Failed to fetch branches:', branchErr)
                }
            } catch (err) {
                // Error handled by errorHandler
            } finally {
                setLoading(false)
            }
        }
        fetchData()
    }, [params.id])

    const handleFileSelect = async (filePath: string) => {
        setSelectedFile(filePath)
        setFileAnalysis(null)
        setAnalyzingFile(true)

        try {
            const cleanPath = filePath.split('/').slice(1).join('/')
            const res = await api.post('/analyze-file', {
                repo_id: params.id,
                file_path: cleanPath
            })
            setFileAnalysis(res.data)
        } catch (err: any) {
            console.error(err)
            setFileAnalysis({
                file: filePath,
                error: 'Failed to analyze file.'
            })
        } finally {
            setAnalyzingFile(false)
        }
    }

    const clearFileSelection = () => {
        setSelectedFile(null)
        setFileAnalysis(null)
    }

    const handleBranchChange = async (branchName: string, branchInfo: any) => {
        setCurrentBranch(branchName)
        setLoading(true)
        errorHandler.clearError()
        
        try {
            // Fetch updated report data for the new branch
            const res = await errorHandler.execute(() => 
                api.get(`/report/${params.id}`, {
                    params: { branch: branchName }
                })
            )
            setData(res.data)
            
            // Clear file selection when switching branches
            clearFileSelection()
        } catch (err: any) {
            // Error handled by errorHandler
        } finally {
            setLoading(false)
        }
    }

    const handleComparisonRequest = (targetBranch: string) => {
        if (targetBranch !== currentBranch) {
            setComparisonBranch(targetBranch)
            setIsComparisonModalOpen(true)
        }
    }

    const handleExplainComparison = (baseBranch: string, compareBranch: string) => {
        aiExplanation.explainComparison(baseBranch, compareBranch)
    }

    const startResizeRight = useCallback((e: React.MouseEvent) => {
        if ('button' in e && e.button !== 0) return
        resizeRef.current = { dragging: 'right', startX: e.clientX, startLeftWidth: fileTreeWidth, startRightWidth: assistantWidth }
        document.body.style.cursor = 'col-resize'
        document.body.style.userSelect = 'none'
        e.preventDefault()
    }, [assistantWidth, fileTreeWidth])

    const startResizeLeft = useCallback((e: React.MouseEvent) => {
        if ('button' in e && e.button !== 0) return
        resizeRef.current = { dragging: 'left', startX: e.clientX, startLeftWidth: fileTreeWidth, startRightWidth: assistantWidth }
        document.body.style.cursor = 'col-resize'
        document.body.style.userSelect = 'none'
        e.preventDefault()
    }, [assistantWidth, fileTreeWidth])

    useEffect(() => {
        const onMouseMove = (e: MouseEvent) => {
            const state = resizeRef.current
            if (!state.dragging) return

            if (state.dragging === 'right') {
                const delta = state.startX - e.clientX
                const nextWidth = Math.min(640, Math.max(260, state.startRightWidth + delta))
                setAssistantWidth(nextWidth)
                return
            }

            if (state.dragging === 'left') {
                const delta = e.clientX - state.startX
                const nextWidth = Math.min(520, Math.max(240, state.startLeftWidth + delta))
                setFileTreeWidth(nextWidth)
            }
        }

        const stopDragging = () => {
            if (!resizeRef.current.dragging) return
            resizeRef.current.dragging = null
            document.body.style.cursor = ''
            document.body.style.userSelect = ''
        }

        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('mouseup', stopDragging)
        return () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('mouseup', stopDragging)
            stopDragging()
        }
    }, [])

    if (loading) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-background">
                <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
                <div className="text-muted-foreground animate-pulse">Analyzing Repository Architecture...</div>
            </div>
        )
    }

    if (errorHandler.hasError || !data) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <ErrorFallback
                    error={errorHandler.error ? new Error(errorHandler.getErrorMessage() || 'Unknown error') : new Error('No data found')}
                    type={errorHandler.isNetworkError ? 'network' : 
                          errorHandler.isAPIError ? 'api' : 'generic'}
                    resetErrorBoundary={() => window.location.reload()}
                    showRetry={true}
                    showHome={true}
                    title="Failed to Load Report"
                    size="lg"
                />
            </div>
        )
    }

    return (
        <ErrorBoundary level="page">
            <div className="min-h-screen bg-background text-foreground font-sans selection:bg-primary/30">
                {/* Top Navigation Bar */}
                <ErrorBoundary level="section">
                    <header className="sticky top-0 z-40 w-full border-b border-white/10 bg-background/80 backdrop-blur-xl">
                        <div className="flex h-16 w-full items-center justify-between px-6">
                            <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
                                <div className="h-8 w-8 rounded-lg bg-primary/20 flex items-center justify-center">
                                    <Activity className="h-5 w-5 text-primary" />
                                </div>
                                Code MRI <span className="text-muted-foreground font-normal text-sm ml-2">/ Report / {params.id.substring(0, 8)}</span>
                            </div>
                            
                            <div className="flex items-center gap-4">
                                {/* Branch Selector */}
                                {branches.length > 0 && (
                                    <ErrorBoundary level="component">
                                        <div className="flex items-center gap-2">
                                            <BranchSelector
                                                repoId={params.id}
                                                currentBranch={currentBranch}
                                                branches={branches}
                                                onBranchChange={handleBranchChange}
                                            />
                                            
                                            {/* Branch Comparison Button */}
                                            {branches.length > 1 && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => {
                                                        // Find a different branch to compare with
                                                        const otherBranch = branches.find(b => b.name !== currentBranch)
                                                        if (otherBranch) {
                                                            handleComparisonRequest(otherBranch.name)
                                                        }
                                                    }}
                                                    className="gap-2"
                                                >
                                                    <GitCompare className="h-4 w-4" />
                                                    Compare
                                                </Button>
                                            )}
                                        </div>
                                    </ErrorBoundary>
                                )}
                                
                                {/* Technology Tags */}
                                {data?.technologies && data.technologies.length > 0 && (
                                    <div className="flex items-center gap-2">
                                        {data.technologies.map((tech) => (
                                            <span 
                                                key={tech} 
                                                className="px-3 py-1.5 text-xs rounded-lg bg-primary/10 text-primary border border-primary/20 font-medium uppercase tracking-wider"
                                            >
                                                {tech}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                
                                <Button size="sm" onClick={() => window.location.href = '/'}>New Scan</Button>
                            </div>
                        </div>
                    </header>
                </ErrorBoundary>

            <div className="flex h-[calc(100vh-4rem)]">
                {/* Left Sidebar - File Tree */}
                <ErrorBoundary level="section">
                    <aside
                        className="border-r border-white/10 bg-black/20 overflow-y-auto hidden lg:block custom-scrollbar"
                        style={{ width: fileTreeWidth }}
                    >
                        <div className="p-4 border-b border-white/10 bg-white/5">
                            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Project Structure</h2>
                            <p className="text-xs text-muted-foreground/60 mt-1">{data.metrics.total_files} files • {data.metrics.total_loc.toLocaleString()} LOC</p>
                        </div>
                        <FileTree 
                            data={data.tree} 
                            onFileSelect={handleFileSelect}
                            selectedFile={selectedFile}
                        />
                    </aside>
                </ErrorBoundary>

                {/* VS Code-style vertical splitter (File Tree) */}
                <div
                    className="hidden lg:flex w-2 h-full cursor-col-resize group hover:bg-primary/10 transition-colors"
                    onMouseDown={startResizeLeft}
                    role="separator"
                    aria-orientation="vertical"
                    aria-label="Resize project structure panel"
                >
                    <div className="mx-auto h-full w-px bg-white/10 group-hover:bg-primary/30" />
                </div>

                {/* Main Content */}
                <main className="flex-1 overflow-y-auto custom-scrollbar">
                    <div className="p-6 lg:p-8 max-w-6xl mx-auto space-y-6">
                        
                        {/* Branch Context Indicator */}
                        {currentBranch && (
                            <div className="glass-card rounded-xl p-4 flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <GitBranch className="h-5 w-5 text-primary" />
                                    <div>
                                        <div className="text-sm font-medium">Current Branch</div>
                                        <div className="font-mono text-lg text-primary">{currentBranch}</div>
                                    </div>
                                </div>
                                {branches.length > 1 && (
                                    <div className="text-xs text-muted-foreground">
                                        {branches.length - 1} other branch{branches.length > 2 ? 'es' : ''} available
                                    </div>
                                )}
                            </div>
                        )}
                        
                        {/* Overview Section */}
                        <ErrorBoundary level="section">
                            <section className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                                {/* Grade & Score */}
                                <div className="lg:col-span-1 glass-card rounded-xl p-6 flex flex-col items-center justify-center text-center space-y-4">
                                    <GradeCircle grade={data.metrics.grade} />
                                    <div>
                                        <div className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Health Score</div>
                                        <div className="text-2xl font-bold text-foreground">{data.scoring?.final_score.toFixed(0) || 0}/100</div>
                                    </div>
                                </div>

                                {/* Key Metrics */}
                                <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <StatCard label="Total Files" value={data.metrics.total_files} icon={FileCode} />
                                    <StatCard label="Lines of Code" value={data.metrics.total_loc.toLocaleString()} icon={Terminal} />
                                    <StatCard label="Issues Found" value={data.issues.length} icon={AlertTriangle} trend={data.issues.length > 0 ? "Requires Attention" : "Clean"} />
                                    <StatCard label="Complexity" value={data.metrics.complexity.toFixed(1)} icon={Cpu} />
                                    <StatCard label="Maintainability" value={data.metrics.maintainability.toFixed(1)} icon={Layers} />
                                    <StatCard label="Documentation" value={`${data.metrics.docs_coverage.toFixed(0)}%`} icon={Box} />
                                </div>
                            </section>
                        </ErrorBoundary>

                        {/* AI Summary */}
                        <div className="glass-card rounded-xl p-6">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="text-lg font-semibold flex items-center gap-2">
                                    <ShieldCheck className="w-5 h-5 text-primary" />
                                    AI Executive Summary
                                </h3>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => aiExplanation.explainGrading('overall', data.scoring)}
                                    disabled={aiExplanation.loading}
                                    className="gap-2"
                                >
                                    {aiExplanation.loading ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <Brain className="h-4 w-4" />
                                    )}
                                    {aiExplanation.loading ? 'Thinking...' : 'Explain'}
                                </Button>
                            </div>
                            <div className="text-muted-foreground leading-relaxed">
                                <MarkdownRenderer content={String(data.summary)} />
                            </div>
                        </div>

                        {/* Enhanced Score Breakdown */}
                        {data.scoring && (
                            <ErrorBoundary level="section">
                                <div className="glass-card rounded-xl p-6">
                                    <div className="flex items-center justify-between mb-6">
                                        <h3 className="text-lg font-semibold flex items-center gap-2">
                                            <TrendingUp className="w-5 h-5 text-primary" />
                                            Detailed Score Analysis
                                        </h3>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => aiExplanation.explainGrading('detailed', data.scoring)}
                                            disabled={aiExplanation.loading}
                                            className="gap-2"
                                        >
                                            {aiExplanation.loading ? (
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                                <Brain className="h-4 w-4" />
                                            )}
                                            {aiExplanation.loading ? 'Analyzing...' : 'Explain Scores'}
                                        </Button>
                                    </div>
                                    
                                    {/* Convert existing scoring data to enhanced format */}
                                    <ScoreBreakdown
                                        scoreData={{
                                            overall_grade: data.metrics.grade,
                                            overall_score: data.scoring.final_score,
                                            category_scores: {
                                                readability: {
                                                    name: 'Readability',
                                                    score: data.scoring.category_scores.readability,
                                                    weight: 0.25,
                                                    contributing_factors: ['Code structure', 'Naming conventions', 'Comment quality'],
                                                    improvement_potential: Math.max(0, 90 - data.scoring.category_scores.readability)
                                                },
                                                complexity: {
                                                    name: 'Complexity',
                                                    score: data.scoring.category_scores.complexity,
                                                    weight: 0.20,
                                                    contributing_factors: ['Cyclomatic complexity', 'Nesting depth', 'Function size'],
                                                    improvement_potential: Math.max(0, 85 - data.scoring.category_scores.complexity)
                                                },
                                                maintainability: {
                                                    name: 'Maintainability',
                                                    score: data.metrics.maintainability,
                                                    weight: 0.20,
                                                    contributing_factors: ['Modularity', 'Coupling', 'Cohesion'],
                                                    improvement_potential: Math.max(0, 85 - data.metrics.maintainability)
                                                },
                                                documentation: {
                                                    name: 'Documentation',
                                                    score: data.scoring.category_scores.docs_coverage,
                                                    weight: 0.15,
                                                    contributing_factors: ['README quality', 'Inline documentation', 'API docs'],
                                                    improvement_potential: Math.max(0, 90 - data.scoring.category_scores.docs_coverage)
                                                },
                                                security: {
                                                    name: 'Security',
                                                    score: data.scoring.category_scores.security,
                                                    weight: 0.10,
                                                    contributing_factors: ['Vulnerability detection', 'Secret scanning', 'Dependency analysis'],
                                                    improvement_potential: Math.max(0, 95 - data.scoring.category_scores.security)
                                                },
                                                performance: {
                                                    name: 'Performance',
                                                    score: 75, // Default since not in current data
                                                    weight: 0.10,
                                                    contributing_factors: ['Code efficiency', 'Resource usage patterns'],
                                                    improvement_potential: 15
                                                }
                                            },
                                            recommendations: [
                                                {
                                                    category: 'readability',
                                                    priority: 'MEDIUM' as const,
                                                    title: 'Improve code documentation',
                                                    description: 'Add more descriptive comments and documentation to enhance code readability.',
                                                    estimated_impact: 5.2,
                                                    effort_level: 'EASY' as const,
                                                    specific_files: []
                                                }
                                            ]
                                        }}
                                        onExplainScore={(category) => aiExplanation.explainGrading(category, data.scoring)}
                                        showTrends={false}
                                    />
                                </div>
                            </ErrorBoundary>
                        )}

                        {/* Context Inspector */}
                        <div className="glass-card rounded-xl p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                                    <Terminal className="h-4 w-4" /> Context Inspector
                                </h2>
                                {selectedFile && (
                                    <Button variant="ghost" size="sm" onClick={clearFileSelection} className="h-6 w-6 p-0">
                                        <X className="h-4 w-4" />
                                    </Button>
                                )}
                            </div>
                            
                            {!selectedFile && (
                                <div className="text-center py-12 text-muted-foreground">
                                    <FileCode className="h-12 w-12 mx-auto mb-3 opacity-30" />
                                    <div className="font-mono text-sm">AWAITING_SELECTION...</div>
                                    <p className="text-xs mt-2 opacity-60">Select a file from the tree to analyze</p>
                                </div>
                            )}

                            {selectedFile && analyzingFile && (
                                <div className="text-center py-12">
                                    <Loader2 className="h-12 w-12 mx-auto mb-3 animate-spin text-primary" />
                                    <div className="font-mono text-sm text-muted-foreground">Analyzing {selectedFile.split('/').pop()}...</div>
                                </div>
                            )}

                            {selectedFile && !analyzingFile && fileAnalysis && (
                                <div className="space-y-4">
                                    {/* File Header */}
                                    <div className="flex items-center gap-2 p-4 bg-white/5 rounded-lg border border-white/10">
                                        <FileCode className="h-5 w-5 text-primary flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium text-sm truncate font-mono">{fileAnalysis.file}</div>
                                            {fileAnalysis.metrics && (
                                                <div className="text-xs text-muted-foreground mt-1">
                                                    {fileAnalysis.metrics.loc} LOC • {fileAnalysis.metrics.comments} comments • CC: {typeof fileAnalysis.metrics.complexity === 'number' ? fileAnalysis.metrics.complexity.toFixed(1) : fileAnalysis.metrics.complexity}
                                                </div>
                                            )}
                                        </div>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setIsModalOpen(true)}
                                            className="gap-2 flex-shrink-0"
                                        >
                                            <Eye className="h-4 w-4" />
                                            View Code
                                        </Button>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => aiExplanation.explainCode(fileAnalysis.file)}
                                            disabled={aiExplanation.loading}
                                            className="gap-2 flex-shrink-0"
                                        >
                                            {aiExplanation.loading ? (
                                                <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                                <Brain className="h-4 w-4" />
                                            )}
                                            {aiExplanation.loading ? 'Analyzing...' : 'Explain'}
                                        </Button>
                                        {fileAnalysis.truncated && (
                                            <span className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded border border-yellow-500/30">Truncated</span>
                                        )}
                                    </div>

                                    {fileAnalysis.error ? (
                                        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                                            {fileAnalysis.error}
                                        </div>
                                    ) : (
                                        <>
                                            {/* Purpose */}
                                            {fileAnalysis.purpose && (
                                                <div className="p-4 bg-white/5 rounded-lg border border-white/10">
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Purpose</div>
                                                    <div className="text-sm font-medium text-primary">{fileAnalysis.purpose}</div>
                                                </div>
                                            )}

                                            {/* Summary */}
                                            {fileAnalysis.summary && (
                                                <div className="p-4 bg-white/5 rounded-lg border border-white/10">
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Summary</div>
                                                    <div className="text-sm leading-relaxed">
                                                        <MarkdownRenderer content={String(fileAnalysis.summary || '')} />
                                                    </div>
                                                </div>
                                            )}

                                            {/* Key Elements */}
                                            {fileAnalysis.key_elements && fileAnalysis.key_elements.length > 0 && (
                                                <div className="p-4 bg-white/5 rounded-lg border border-white/10">
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Key Elements</div>
                                                    <div className="space-y-2">
                                                        {fileAnalysis.key_elements.map((el, i) => (
                                                            <div key={i} className="text-sm p-3 bg-black/30 rounded border border-white/5">
                                                                {typeof el === 'string' ? el : (
                                                                    <>
                                                                        <span className="font-mono text-primary font-medium">{el.name}</span>
                                                                        {el.description && <span className="text-muted-foreground"> - {el.description}</span>}
                                                                    </>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Patterns */}
                                            {fileAnalysis.patterns && (
                                                <div className="p-4 bg-white/5 rounded-lg border border-white/10">
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Patterns & Libraries</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        <MarkdownRenderer content={String(fileAnalysis.patterns || '')} />
                                                    </div>
                                                </div>
                                            )}

                                            {/* Quality Notes */}
                                            {fileAnalysis.quality_notes && (
                                                <div className="p-4 bg-white/5 rounded-lg border border-white/10">
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Quality Notes</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        <MarkdownRenderer content={String(fileAnalysis.quality_notes || '')} />
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Issues List */}
                        <div className="glass-card rounded-xl overflow-hidden">
                            <div className="p-4 border-b border-white/10 bg-white/5 flex items-center justify-between">
                                <h3 className="font-semibold flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4 text-yellow-400" />
                                    Detected Issues
                                    <span className="bg-white/10 text-xs px-2 py-0.5 rounded-full">{data.issues.length}</span>
                                </h3>
                            </div>
                            <div className="p-4 space-y-3 max-h-96 overflow-y-auto custom-scrollbar">
                                {data.issues.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                                        <CheckCircle2 className="w-12 h-12 mb-2 text-green-500/50" />
                                        <p>No major issues detected.</p>
                                    </div>
                                ) : (
                                    data.issues.map((issue, idx) => (
                                        <IssueCard key={idx} issue={issue} />
                                    ))
                                )}
                            </div>
                        </div>

                        {/* Historical Trends */}
                        {branches.length > 0 && (
                            <ErrorBoundary level="section">
                                <HistoricalTrendsPanel
                                    repoId={params.id}
                                    currentBranch={currentBranch}
                                    branches={branches}
                                />
                            </ErrorBoundary>
                        )}
                    </div>
                </main>

                {/* VS Code-style vertical splitter + Right Sidebar (Resizable) */}
                <div
                    className="hidden xl:flex w-2 h-full cursor-col-resize group hover:bg-primary/10 transition-colors"
                    onMouseDown={startResizeRight}
                    role="separator"
                    aria-orientation="vertical"
                    aria-label="Resize AI assistant panel"
                >
                    <div className="mx-auto h-full w-px bg-white/10 group-hover:bg-primary/30" />
                </div>

                <ErrorBoundary level="section">
                    <aside
                        className="hidden xl:flex flex-col bg-black/20 border-l border-white/10"
                        style={{ width: assistantWidth }}
                    >
                        <AIAssistant repoId={params.id} />
                    </aside>
                </ErrorBoundary>
            </div>
            
            {/* Modals */}
            <ErrorBoundary level="component">
                {/* Code View Modal */}
                <CodeViewModal
                    isOpen={isModalOpen}
                    onClose={() => setIsModalOpen(false)}
                    repoId={params.id}
                    filePath={selectedFile || ''}
                    fileAnalysis={fileAnalysis}
                />
                
                {/* Branch Comparison Modal */}
                <BranchComparisonModal
                    isOpen={isComparisonModalOpen}
                    onClose={() => setIsComparisonModalOpen(false)}
                    repoId={params.id}
                    baseBranch={currentBranch}
                    compareBranch={comparisonBranch}
                    onExplainComparison={handleExplainComparison}
                />
                
                {/* AI Explanation Modal */}
                <AIExplanationModal
                    isOpen={aiExplanation.isModalOpen}
                    onClose={aiExplanation.closeModal}
                    repoId={params.id}
                    explanationType={aiExplanation.explanationType || 'grading'}
                    context={aiExplanation.context}
                />
            </ErrorBoundary>
            </div>
        </ErrorBoundary>
    )
}

function FolderIcon({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 2H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2Z" />
        </svg>
    )
}
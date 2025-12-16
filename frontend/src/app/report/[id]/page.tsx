'use client'

import { useCallback, useEffect, useState } from 'react'
import { FileTree } from '@/components/FileTree'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'
import { CodeViewModal } from '@/components/CodeViewModal'
import { GitBranch, ShieldCheck, Cpu, AlertTriangle, Terminal, FileCode, Loader2, X, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'

// Types
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

// Grade color helper
const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return 'text-green-400'
    if (grade.startsWith('B')) return 'text-blue-400'
    if (grade.startsWith('C')) return 'text-yellow-400'
    if (grade.startsWith('D')) return 'text-orange-400'
    return 'text-red-400'
}

const getSeverityColor = (severity: string) => {
    switch (severity) {
        case 'HIGH': return 'bg-red-500/20 text-red-400 border-red-500/30'
        case 'MEDIUM': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
        case 'LOW': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
        default: return 'bg-gray-500/20 text-gray-400'
    }
}

// Metric Card Component
const MetricCard = ({ label, value, color }: { label: string, value: number, color: string }) => (
    <div className="text-center">
        <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider mb-2">{label}</div>
        <div className={`text-3xl font-bold ${color}`}>{value}</div>
    </div>
)

// AI Assistant Panel
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
            <div className="p-4 border-b border-white/10">
                <h3 className="font-semibold text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                    AI ASSISTANT
                </h3>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
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
                            <div className="bg-white/5 p-3 rounded">
                                <MarkdownRenderer content={String(m.text || '')} />
                            </div>
                        )}
                    </div>
                ))}
                {loading && <div className="text-xs text-muted-foreground animate-pulse font-mono">Processing query...</div>}
            </div>
            <form onSubmit={handleSend} className="p-4 border-t border-white/10">
                <div className="flex gap-2">
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

export default function ReportPage({ params }: { params: { id: string } }) {
    const [data, setData] = useState<ReportData | null>(null)
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(true)
    const [selectedFile, setSelectedFile] = useState<string | null>(null)
    const [fileAnalysis, setFileAnalysis] = useState<FileAnalysis | null>(null)
    const [fileAnalyzing, setFileAnalyzing] = useState(false)
    const [isCodeModalOpen, setIsCodeModalOpen] = useState(false)

    const fetchData = useCallback(async () => {
        try {
            const res = await api.get(`/report/${params.id}`)
            setData(res.data)
            api.post(`/index/${params.id}`).catch(console.error)
            setLoading(false)
        } catch (err) {
            setError('Failed to load report. It may have expired.')
            setLoading(false)
        }
    }, [params.id])

    const handleFileSelect = useCallback(async (filePath: string) => {
        // Remove the root folder name from the path (first segment)
        const pathParts = filePath.split('/')
        const cleanPath = pathParts.length > 1 ? pathParts.slice(1).join('/') : filePath
        
        setSelectedFile(filePath)
        setFileAnalysis(null)
        setFileAnalyzing(true)

        try {
            const res = await api.post('/analyze-file', {
                repo_id: params.id,
                file_path: cleanPath
            })
            setFileAnalysis(res.data)
        } catch (err: any) {
            setFileAnalysis({
                file: cleanPath,
                error: err.response?.data?.detail || 'Failed to analyze file'
            })
        } finally {
            setFileAnalyzing(false)
        }
    }, [params.id])

    const clearFileSelection = () => {
        setSelectedFile(null)
        setFileAnalysis(null)
    }

    useEffect(() => {
        fetchData()
    }, [fetchData])

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="text-center">
                    <Cpu className="h-12 w-12 text-primary animate-pulse mx-auto mb-4" />
                    <div className="text-lg font-medium">Analyzing Repository...</div>
                    <div className="text-sm text-muted-foreground mt-2">Running static analysis</div>
                </div>
            </div>
        )
    }

    if (error) return <div className="min-h-screen flex items-center justify-center text-red-400 bg-background">{error}</div>;
    if (!data) return null;

    return (
        <div className="min-h-screen bg-background">
            {/* Header Bar */}
            <header className="h-14 border-b border-white/10 bg-black/40 flex items-center px-6 justify-between">
                <div className="flex items-center gap-4">
                    <h1 className="text-xl font-bold text-primary">CODE<span className="text-white">MRI</span></h1>
                    <div className="flex items-center gap-2 text-sm">
                        <GitBranch className="h-4 w-4 text-muted-foreground" />
                        <span className="text-muted-foreground">{data.repo_id}</span>
                        <span className="px-2 py-0.5 rounded text-xs bg-primary/20 text-primary border border-primary/30">MASTER</span>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {data.technologies.map(tech => (
                        <span key={tech} className="px-2 py-1 text-xs rounded bg-white/5 text-muted-foreground border border-white/10">
                            {tech}
                        </span>
                    ))}
                </div>
            </header>

            <div className="flex h-[calc(100vh-3.5rem)]">
                {/* Left Sidebar - File Tree */}
                <aside className="w-72 border-r border-white/10 bg-black/20 overflow-y-auto hidden lg:block">
                    <div className="p-4 border-b border-white/10">
                        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Project Structure</h2>
                        <p className="text-xs text-muted-foreground/60 mt-1">Click a file to analyze</p>
                    </div>
                    <FileTree 
                        data={data.tree} 
                        onFileSelect={handleFileSelect}
                        selectedFile={selectedFile}
                    />
                </aside>

                {/* Main Content */}
                <main className="flex-1 overflow-y-auto">
                    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
                        
                        {/* Execution Summary + Grade */}
                        <div className="glass-card rounded-xl p-6">
                            <div className="flex flex-col lg:flex-row gap-6">
                                <div className="flex-1">
                                    <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">Execution Summary</h2>
                                    <div className="text-foreground leading-relaxed">
                                        <MarkdownRenderer content={String(data.summary || '')} />
                                    </div>
                                </div>
                                <div className="flex flex-col items-center justify-center lg:border-l lg:border-white/10 lg:pl-8">
                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Quality Grade</div>
                                    <div className="relative">
                                        <svg className="w-24 h-24" viewBox="0 0 100 100">
                                            <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="8" />
                                            <circle 
                                                cx="50" cy="50" r="45" 
                                                fill="none" 
                                                stroke="currentColor" 
                                                strokeWidth="8"
                                                strokeLinecap="round"
                                                strokeDasharray={`${(data.metrics.readability + data.metrics.complexity + data.metrics.maintainability + data.metrics.docs_coverage) / 4 * 2.83} 283`}
                                                transform="rotate(-90 50 50)"
                                                className={getGradeColor(data.metrics.grade)}
                                            />
                                        </svg>
                                        <div className={`absolute inset-0 flex items-center justify-center text-3xl font-bold ${getGradeColor(data.metrics.grade)}`}>
                                            {data.metrics.grade}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Metrics Grid */}
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <div className="glass-card rounded-xl p-5">
                                <MetricCard label="Readability" value={data.metrics.readability} color="text-green-400" />
                            </div>
                            <div className="glass-card rounded-xl p-5">
                                <MetricCard label="Complexity" value={data.metrics.complexity} color="text-yellow-400" />
                            </div>
                            <div className="glass-card rounded-xl p-5">
                                <MetricCard label="Maintainability" value={data.metrics.maintainability} color="text-blue-400" />
                            </div>
                            <div className="glass-card rounded-xl p-5">
                                <MetricCard label="Docs Coverage" value={data.metrics.docs_coverage} color="text-purple-400" />
                            </div>
                        </div>

                        {/* AI Scoring Agent Analysis */}
                        {data.scoring && (
                            <div className="glass-card rounded-xl p-6 border border-primary/20">
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="w-2 h-2 rounded-full bg-primary animate-pulse"></div>
                                    <h2 className="text-sm font-semibold text-primary uppercase tracking-wider">AI Scoring Agent Analysis</h2>
                                </div>
                                <div className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <div className="flex-1">
                                            <div className="text-sm text-muted-foreground mb-2">Overall Code Quality Score</div>
                                            <div className="flex items-baseline gap-2">
                                                <span className="text-4xl font-bold text-primary">{data.scoring.final_score}</span>
                                                <span className="text-lg text-muted-foreground">/100</span>
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-3 text-xs">
                                            <div className="text-center p-2 rounded bg-white/5">
                                                <div className="text-muted-foreground">Readability</div>
                                                <div className="text-green-400 font-bold">{data.scoring.category_scores.readability}</div>
                                            </div>
                                            <div className="text-center p-2 rounded bg-white/5">
                                                <div className="text-muted-foreground">Complexity</div>
                                                <div className="text-yellow-400 font-bold">{data.scoring.category_scores.complexity}</div>
                                            </div>
                                            <div className="text-center p-2 rounded bg-white/5">
                                                <div className="text-muted-foreground">Docs</div>
                                                <div className="text-purple-400 font-bold">{data.scoring.category_scores.docs_coverage}</div>
                                            </div>
                                            <div className="text-center p-2 rounded bg-white/5">
                                                <div className="text-muted-foreground">Security</div>
                                                <div className="text-red-400 font-bold">{data.scoring.category_scores.security}</div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="border-t border-white/10 pt-4">
                                        <div className="text-sm leading-relaxed text-foreground/90">
                                            <MarkdownRenderer content={String(data.scoring.ai_analysis || '')} />
                                        </div>
                                    </div>
                                </div>
                            </div>
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
                                <div className="text-center py-8 text-muted-foreground">
                                    <FileCode className="h-8 w-8 mx-auto mb-3 opacity-50" />
                                    <div className="font-mono text-sm">AWAITING_SELECTION...</div>
                                    <p className="text-xs mt-2 opacity-60">Select a file from the tree to analyze</p>
                                </div>
                            )}

                            {selectedFile && fileAnalyzing && (
                                <div className="text-center py-8">
                                    <Loader2 className="h-8 w-8 mx-auto mb-3 animate-spin text-primary" />
                                    <div className="font-mono text-sm text-muted-foreground">Analyzing {selectedFile.split('/').pop()}...</div>
                                </div>
                            )}

                            {selectedFile && !fileAnalyzing && fileAnalysis && (
                                <div className="space-y-4">
                                    {/* File Header */}
                                    <div className="flex items-center gap-2 p-3 bg-white/5 rounded-lg">
                                        <FileCode className="h-5 w-5 text-primary" />
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium text-sm truncate">{fileAnalysis.file}</div>
                                            {fileAnalysis.metrics && (
                                                <div className="text-xs text-muted-foreground">
                                                    {fileAnalysis.metrics.loc} LOC • {fileAnalysis.metrics.comments} comments • CC: {typeof fileAnalysis.metrics.complexity === 'number' ? fileAnalysis.metrics.complexity.toFixed(1) : fileAnalysis.metrics.complexity}
                                                </div>
                                            )}
                                        </div>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setIsCodeModalOpen(true)}
                                            className="gap-2"
                                        >
                                            <Eye className="h-4 w-4" />
                                            View Code
                                        </Button>
                                        {fileAnalysis.truncated && (
                                            <span className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">Truncated</span>
                                        )}
                                    </div>

                                    {fileAnalysis.error ? (
                                        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                                            {fileAnalysis.error}
                                        </div>
                                    ) : (
                                        <>
                                            {/* Purpose */}
                                            {fileAnalysis.purpose && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Purpose</div>
                                                    <div className="text-sm font-medium text-primary">{fileAnalysis.purpose}</div>
                                                </div>
                                            )}

                                            {/* Summary */}
                                            {fileAnalysis.summary && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Summary</div>
                                                    <div className="text-sm leading-relaxed">
                                                        <MarkdownRenderer content={String(fileAnalysis.summary || '')} />
                                                    </div>
                                                </div>
                                            )}

                                            {/* Key Elements */}
                                            {fileAnalysis.key_elements && fileAnalysis.key_elements.length > 0 && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Key Elements</div>
                                                    <div className="space-y-2">
                                                        {fileAnalysis.key_elements.map((el, i) => (
                                                            <div key={i} className="text-sm p-2 bg-white/5 rounded">
                                                                {typeof el === 'string' ? el : (
                                                                    <>
                                                                        <span className="font-mono text-primary">{el.name}</span>
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
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Patterns & Libraries</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        <MarkdownRenderer content={String(fileAnalysis.patterns || '')} />
                                                    </div>
                                                </div>
                                            )}

                                            {/* Quality Notes */}
                                            {fileAnalysis.quality_notes && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Quality Notes</div>
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

                        {/* Static Analysis Results */}
                        {data.issues.length > 0 && (
                            <div className="glass-card rounded-xl p-6">
                                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4 flex items-center gap-2">
                                    <AlertTriangle className="h-4 w-4 text-yellow-500" /> Static Analysis Results
                                </h2>
                                <div className="space-y-3">
                                    {data.issues.slice(0, 10).map((issue, i) => (
                                        <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                                            <div className="flex items-center gap-3">
                                                <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(issue.severity)}`}>
                                                    {issue.severity}
                                                </span>
                                                <div>
                                                    <div className="font-medium text-sm">{issue.title}</div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {issue.file} <span className="text-primary">Ln {issue.line}</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <Button variant="outline" size="sm" className="text-xs">
                                                PATCH
                                            </Button>
                                        </div>
                                    ))}
                                    {data.issues.length > 10 && (
                                        <div className="text-center text-sm text-muted-foreground pt-2">
                                            + {data.issues.length - 10} more issues
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Secure Notice */}
                        <div className="p-4 border border-green-500/20 bg-green-500/5 rounded-lg flex items-start gap-4">
                            <ShieldCheck className="h-5 w-5 text-green-500 mt-0.5" />
                            <div>
                                <h4 className="text-sm font-medium text-green-200">Execution Sandbox Active</h4>
                                <p className="text-xs text-green-200/60 mt-1">Code is statically analyzed. No makefiles, npm scripts, or binaries were executed.</p>
                            </div>
                        </div>

                        {/* Mobile File Tree */}
                        <div className="lg:hidden">
                            <h3 className="font-semibold mb-4 text-sm uppercase tracking-wider text-muted-foreground">File Structure</h3>
                            <div className="border border-white/10 rounded-lg overflow-hidden bg-black/20">
                                <FileTree 
                                    data={data.tree} 
                                    onFileSelect={handleFileSelect}
                                    selectedFile={selectedFile}
                                />
                            </div>
                        </div>
                    </div>
                </main>

                {/* Right Sidebar - AI Assistant */}
                <aside className="w-80 border-l border-white/10 bg-black/20 hidden xl:flex flex-col">
                    <AIAssistant repoId={params.id} />
                </aside>
            </div>
            
            {/* Code View Modal */}
            {fileAnalysis && (
                <CodeViewModal
                    isOpen={isCodeModalOpen}
                    onClose={() => setIsCodeModalOpen(false)}
                    repoId={params.id}
                    filePath={selectedFile || ''}
                    fileAnalysis={fileAnalysis}
                />
            )}
        </div>
    )
}

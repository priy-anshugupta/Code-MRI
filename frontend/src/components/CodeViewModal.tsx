'use client'

import React, { useCallback, useEffect, useState, useRef } from 'react'
import { X, FileCode, Loader2, Maximize2, Minimize2, Terminal, Bot, User, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { MarkdownRenderer } from './MarkdownRenderer'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface FileAnalysis {
    file: string
    metrics?: any
    summary?: string
    purpose?: string
    key_elements?: Array<{ name: string; description: string } | string>
    patterns?: string
    quality_notes?: string
    error?: string
    truncated?: boolean
}

interface CodeViewModalProps {
    isOpen: boolean
    onClose: () => void
    repoId: string
    filePath: string
    fileAnalysis: FileAnalysis | null
}

export function CodeViewModal({ isOpen, onClose, repoId, filePath, fileAnalysis }: CodeViewModalProps) {
    const [fileContent, setFileContent] = useState<string>('')
    const [language, setLanguage] = useState<string>('text')
    const [loading, setLoading] = useState(true)
    const [isExpanded, setIsExpanded] = useState(false)
    const [rightTab, setRightTab] = useState<'inspector' | 'chat'>('inspector')
    const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'bot', text: string }>>([])
    const [chatInput, setChatInput] = useState('')
    const [chatLoading, setChatLoading] = useState(false)
    const chatEndRef = useRef<HTMLDivElement>(null)

    const fetchFileContent = useCallback(async () => {
        setLoading(true)
        try {
            const cleanPath = filePath.split('/').slice(1).join('/')
            const res = await api.post('/file-content', {
                repo_id: repoId,
                file_path: cleanPath
            })
            setFileContent(res.data.content)
            setLanguage(res.data.language)
        } catch (err) {
            console.error('Failed to load file content:', err)
            setFileContent('// Failed to load file content')
        } finally {
            setLoading(false)
        }
    }, [filePath, repoId])

    useEffect(() => {
        if (isOpen && filePath) {
            fetchFileContent()
            setChatMessages([])
            setRightTab('inspector')
        }
    }, [isOpen, filePath, fetchFileContent])

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [chatMessages])

    const handleChatSend = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!chatInput.trim() || chatLoading) return

        const userMessage = chatInput
        setChatMessages(prev => [...prev, { role: 'user', text: userMessage }])
        setChatInput('')
        setChatLoading(true)

        try {
            const cleanPath = filePath.split('/').slice(1).join('/')
            const res = await api.post('/chat-file', {
                repo_id: repoId,
                file_path: cleanPath,
                message: userMessage
            })
            setChatMessages(prev => [...prev, { role: 'bot', text: res.data.response }])
        } catch (err) {
            setChatMessages(prev => [...prev, { role: 'bot', text: 'Error: Could not get response.' }])
        } finally {
            setChatLoading(false)
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className={cn(
                    "bg-[#0D0D12] border border-white/10 rounded-xl shadow-2xl flex flex-col overflow-hidden transition-all duration-300",
                    isExpanded ? "w-full h-full" : "w-[95vw] h-[90vh] max-w-7xl"
                )}
            >
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/5">
                    <div className="flex items-center gap-4">
                        <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                            <FileCode className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-foreground tracking-tight">{filePath.split('/').pop()}</h2>
                            <p className="text-xs text-muted-foreground font-mono">{filePath}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" onClick={() => setIsExpanded(!isExpanded)} className="hover:bg-white/10">
                            {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                        </Button>
                        <Button variant="ghost" size="icon" onClick={onClose} className="hover:bg-red-500/20 hover:text-red-400">
                            <X className="h-5 w-5" />
                        </Button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Code View */}
                    <div className="flex-1 overflow-hidden flex flex-col border-r border-white/10 bg-[#0D0D12]">
                        <div className="flex-1 overflow-auto custom-scrollbar p-0">
                            {loading ? (
                                <div className="h-full flex items-center justify-center">
                                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                </div>
                            ) : (
                                <div className="p-6">
                                    <MarkdownRenderer content={`\`\`\`${language}\n${fileContent}\n\`\`\``} />
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right Panel with Tabs */}
                    <div className="w-[400px] flex flex-col bg-[#121217]">
                        {/* Tab Switcher */}
                        <div className="flex border-b border-white/10 bg-white/5">
                            <button
                                onClick={() => setRightTab('inspector')}
                                className={cn(
                                    "flex-1 px-4 py-3 text-sm font-medium transition-all relative",
                                    rightTab === 'inspector' 
                                        ? "text-primary bg-white/5" 
                                        : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                                )}
                            >
                                <Terminal className="w-4 h-4 inline-block mr-2" />
                                Inspector
                                {rightTab === 'inspector' && (
                                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
                                )}
                            </button>
                            <button
                                onClick={() => setRightTab('chat')}
                                className={cn(
                                    "flex-1 px-4 py-3 text-sm font-medium transition-all relative",
                                    rightTab === 'chat' 
                                        ? "text-primary bg-white/5" 
                                        : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                                )}
                            >
                                <Bot className="w-4 h-4 inline-block mr-2" />
                                AI Chat
                                {rightTab === 'chat' && (
                                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
                                )}
                            </button>
                        </div>

                        {/* Context Inspector Tab */}
                        {rightTab === 'inspector' && (
                        <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                            {!fileAnalysis ? (
                                <div className="text-center text-muted-foreground py-10 px-4">
                                    <FileCode className="w-12 h-12 mx-auto mb-4 opacity-20" />
                                    <p className="text-sm">Loading analysis...</p>
                                </div>
                            ) : fileAnalysis.error ? (
                                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-xs">
                                    {fileAnalysis.error}
                                </div>
                            ) : (
                                <>
                                    {/* File Metrics */}
                                    {fileAnalysis.metrics && (
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Metrics</div>
                                            <div className="text-xs grid grid-cols-3 gap-2">
                                                <div>
                                                    <div className="text-muted-foreground">LOC</div>
                                                    <div className="text-primary font-semibold">{fileAnalysis.metrics.loc}</div>
                                                </div>
                                                <div>
                                                    <div className="text-muted-foreground">Comments</div>
                                                    <div className="text-primary font-semibold">{fileAnalysis.metrics.comments}</div>
                                                </div>
                                                <div>
                                                    <div className="text-muted-foreground">Complexity</div>
                                                    <div className="text-primary font-semibold">
                                                        {typeof fileAnalysis.metrics.complexity === 'number' 
                                                            ? fileAnalysis.metrics.complexity.toFixed(1) 
                                                            : fileAnalysis.metrics.complexity}
                                                    </div>
                                                </div>
                                            </div>
                                            {fileAnalysis.truncated && (
                                                <div className="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-1 rounded border border-yellow-500/30 mt-2">
                                                    ⚠️ File truncated for analysis
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Purpose */}
                                    {fileAnalysis.purpose && (
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Purpose</div>
                                            <div className="text-sm font-medium text-primary">{fileAnalysis.purpose}</div>
                                        </div>
                                    )}

                                    {/* Summary */}
                                    {fileAnalysis.summary && (
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Summary</div>
                                            <div className="text-xs leading-relaxed">
                                                <MarkdownRenderer content={String(fileAnalysis.summary || '')} />
                                            </div>
                                        </div>
                                    )}

                                    {/* Key Elements */}
                                    {fileAnalysis.key_elements && fileAnalysis.key_elements.length > 0 && (
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Key Elements</div>
                                            <div className="space-y-1.5">
                                                {fileAnalysis.key_elements.map((el, i) => (
                                                    <div key={i} className="text-xs p-2 bg-black/30 rounded border border-white/5">
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
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Patterns & Libraries</div>
                                            <div className="text-xs text-muted-foreground">
                                                <MarkdownRenderer content={String(fileAnalysis.patterns || '')} />
                                            </div>
                                        </div>
                                    )}

                                    {/* Quality Notes */}
                                    {fileAnalysis.quality_notes && (
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Quality Notes</div>
                                            <div className="text-xs text-muted-foreground">
                                                <MarkdownRenderer content={String(fileAnalysis.quality_notes || '')} />
                                            </div>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                        )}

                        {/* AI Chat Tab */}
                        {rightTab === 'chat' && (
                        <div className="flex-1 flex flex-col overflow-hidden">
                            <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                                {chatMessages.length === 0 && (
                                    <div className="text-center text-muted-foreground py-10 px-4">
                                        <Bot className="w-12 h-12 mx-auto mb-4 opacity-20" />
                                        <p className="text-sm">Ask questions about this file. I can explain the logic, find bugs, or suggest improvements.</p>
                                    </div>
                                )}
                                
                                {chatMessages.map((msg, idx) => (
                                    <div key={idx} className={cn("flex gap-3", msg.role === 'user' ? "flex-row-reverse" : "")}>
                                        <div className={cn(
                                            "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                                            msg.role === 'user' ? "bg-primary/20 text-primary" : "bg-blue-500/20 text-blue-400"
                                        )}>
                                            {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                                        </div>
                                        <div className={cn(
                                            "rounded-lg p-3 text-sm max-w-[85%]",
                                            msg.role === 'user' ? "bg-primary/10 text-foreground" : "bg-white/5 text-muted-foreground"
                                        )}>
                                            <MarkdownRenderer content={msg.text} />
                                        </div>
                                    </div>
                                ))}
                                {chatLoading && (
                                    <div className="flex gap-3">
                                        <div className="w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center flex-shrink-0">
                                            <Bot className="w-4 h-4" />
                                        </div>
                                        <div className="bg-white/5 rounded-lg p-3">
                                            <Loader2 className="w-4 h-4 animate-spin" />
                                        </div>
                                    </div>
                                )}
                                <div ref={chatEndRef} />
                            </div>

                            <div className="p-4 border-t border-white/10 bg-white/5">
                                <form onSubmit={handleChatSend} className="relative">
                                    <input
                                        type="text"
                                        value={chatInput}
                                        onChange={(e) => setChatInput(e.target.value)}
                                        placeholder="Ask about this code..."
                                        className="w-full bg-black/20 border border-white/10 rounded-lg pl-4 pr-10 py-3 text-sm focus:outline-none focus:border-primary/50 transition-colors"
                                    />
                                    <Button 
                                        type="submit" 
                                        size="icon"
                                        variant="ghost"
                                        className="absolute right-1 top-1 h-8 w-8 hover:bg-primary/20 hover:text-primary"
                                        disabled={!chatInput.trim() || chatLoading}
                                    >
                                        <Send className="w-4 h-4" />
                                    </Button>
                                </form>
                            </div>
                        </div>
                        )}
                    </div>
                </div>
            </motion.div>
        </div>
    )
}

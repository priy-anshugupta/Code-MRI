'use client'

import React, { useState, useEffect } from 'react'
import { X, MessageSquare, FileCode, Loader2, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { MarkdownRenderer } from './MarkdownRenderer'

interface FileAnalysis {
    file: string
    metrics?: any
    summary?: string
    purpose?: string
    key_elements?: Array<{ name: string; description: string } | string>
    patterns?: string
    quality_notes?: string
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
    const [mode, setMode] = useState<'summary' | 'chat'>('summary')
    const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'bot', text: string }>>([])
    const [chatInput, setChatInput] = useState('')
    const [chatLoading, setChatLoading] = useState(false)

    useEffect(() => {
        if (isOpen && filePath) {
            fetchFileContent()
            setMode('summary')
            setChatMessages([])
        }
    }, [isOpen, filePath, repoId])

    const fetchFileContent = async () => {
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
    }

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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className="w-[95vw] h-[90vh] bg-background border border-white/10 rounded-xl shadow-2xl flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        <FileCode className="h-5 w-5 text-primary" />
                        <div>
                            <h2 className="text-lg font-semibold">{filePath.split('/').pop()}</h2>
                            <p className="text-xs text-muted-foreground">{filePath}</p>
                        </div>
                    </div>
                    <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
                        <X className="h-4 w-4" />
                    </Button>
                </div>

                {/* Content */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Left: Code */}
                    <div className="flex-1 border-r border-white/10 overflow-hidden flex flex-col">
                        <div className="px-4 py-2 bg-white/5 border-b border-white/10">
                            <div className="text-xs font-mono text-muted-foreground">
                                Language: {language}
                            </div>
                        </div>
                        <div className="flex-1 overflow-auto">
                            {loading ? (
                                <div className="flex items-center justify-center h-full">
                                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                </div>
                            ) : (
                                <pre className="p-4 text-sm font-mono leading-relaxed">
                                    <code className={`language-${language}`}>
                                        {fileContent}
                                    </code>
                                </pre>
                            )}
                        </div>
                    </div>

                    {/* Right: Summary or Chat */}
                    <div className="w-96 flex flex-col">
                        {/* Tab Selector */}
                        <div className="flex border-b border-white/10">
                            <button
                                onClick={() => setMode('summary')}
                                className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                                    mode === 'summary' 
                                        ? 'bg-primary/20 text-primary border-b-2 border-primary' 
                                        : 'text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                Summary
                            </button>
                            <button
                                onClick={() => setMode('chat')}
                                className={`flex-1 px-4 py-2 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                                    mode === 'chat' 
                                        ? 'bg-primary/20 text-primary border-b-2 border-primary' 
                                        : 'text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                <MessageSquare className="h-4 w-4" />
                                AI Chat
                            </button>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 overflow-auto">
                            {mode === 'summary' ? (
                                <div className="p-4 space-y-4">
                                    {fileAnalysis ? (
                                        <>
                                            {fileAnalysis.purpose && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Purpose</div>
                                                    <div className="text-sm font-medium text-primary">{fileAnalysis.purpose}</div>
                                                </div>
                                            )}

                                            {fileAnalysis.summary && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Summary</div>
                                                    <div className="text-sm leading-relaxed">
                                                        <MarkdownRenderer content={String(fileAnalysis.summary || '')} />
                                                    </div>
                                                </div>
                                            )}

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

                                            {fileAnalysis.patterns && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Patterns & Libraries</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        <MarkdownRenderer content={String(fileAnalysis.patterns || '')} />
                                                    </div>
                                                </div>
                                            )}

                                            {fileAnalysis.quality_notes && (
                                                <div>
                                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Quality Notes</div>
                                                    <div className="text-sm text-muted-foreground">
                                                        <MarkdownRenderer content={String(fileAnalysis.quality_notes || '')} />
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <div className="text-center text-muted-foreground text-sm py-8">
                                            No analysis available
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="flex flex-col h-full">
                                    <div className="flex-1 overflow-y-auto p-4 space-y-3">
                                        {chatMessages.length === 0 && (
                                            <div className="text-center text-muted-foreground text-sm py-8">
                                                Ask me anything about this file...
                                            </div>
                                        )}
                                        {chatMessages.map((msg, i) => (
                                            <div key={i} className={msg.role === 'user' ? 'ml-4' : ''}>
                                                {msg.role === 'user' ? (
                                                    <div className="bg-primary/20 text-primary-foreground p-3 rounded">
                                                        {msg.text}
                                                    </div>
                                                ) : (
                                                    <div className="bg-white/5 p-3 rounded">
                                                        <MarkdownRenderer content={String(msg.text)} />
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                        {chatLoading && (
                                            <div className="text-xs text-muted-foreground animate-pulse">Thinking...</div>
                                        )}
                                    </div>
                                    <form onSubmit={handleChatSend} className="p-4 border-t border-white/10">
                                        <div className="flex gap-2">
                                            <input
                                                className="flex-1 bg-white/5 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
                                                placeholder="Ask about this file..."
                                                value={chatInput}
                                                onChange={e => setChatInput(e.target.value)}
                                                disabled={chatLoading}
                                            />
                                            <Button type="submit" size="sm" disabled={chatLoading || !chatInput.trim()}>
                                                <Send className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </form>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

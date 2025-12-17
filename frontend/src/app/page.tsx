'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight, Loader2, Search, Github, Terminal, ShieldCheck, Zap, Code2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function Home() {
    const [url, setUrl] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [mounted, setMounted] = useState(false)
    const router = useRouter()

    useEffect(() => {
        setMounted(true)
    }, [])

    const handleAnalyze = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!url) {
            setError('Please paste a repository URL.')
            return
        }

        setLoading(true)
        setError('')

        try {
            const response = await api.post('/analyze', { url })
            const repoId = response.data.repo_id
            router.push(`/report/${repoId}`)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Analysis failed. Please try a public GitHub URL.')
        } finally {
            setLoading(false)
        }
    }

    if (!mounted) return null

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-6 relative overflow-hidden bg-background selection:bg-primary/30">
            {/* Dynamic Background */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />
                <div className="absolute bottom-0 left-0 right-0 h-[500px] bg-gradient-to-t from-background to-transparent" />
                
                {/* Animated Grid */}
                <div className="absolute inset-0 bg-[url('/grid.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))]" />
                
                {/* Floating Orbs */}
                <motion.div 
                    animate={{ 
                        x: [0, 100, 0],
                        y: [0, -50, 0],
                        opacity: [0.3, 0.5, 0.3]
                    }}
                    transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
                    className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-[128px]" 
                />
                <motion.div 
                    animate={{ 
                        x: [0, -100, 0],
                        y: [0, 50, 0],
                        opacity: [0.2, 0.4, 0.2]
                    }}
                    transition={{ duration: 15, repeat: Infinity, ease: "easeInOut", delay: 2 }}
                    className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[128px]" 
                />
            </div>

            <div className="z-10 w-full max-w-4xl mx-auto flex flex-col items-center text-center space-y-12">
                
                {/* Hero Section */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="space-y-6"
                >
                    <div className="inline-flex items-center px-4 py-1.5 rounded-full border border-primary/20 bg-primary/5 text-sm font-medium text-primary backdrop-blur-sm">
                        <span className="relative flex h-2 w-2 mr-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                        </span>
                        System Online v2.0
                    </div>
                    
                    <h1 className="text-6xl md:text-8xl font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-b from-white via-white/90 to-white/50 pb-2">
                        Code MRI
                    </h1>
                    
                    <p className="text-xl md:text-2xl text-muted-foreground max-w-2xl mx-auto leading-relaxed font-light">
                        Autonomous static analysis & intelligence engine.
                        <br />
                        <span className="text-foreground/80">Scan. Diagnose. Optimize.</span>
                    </p>
                </motion.div>

                {/* Search Interface */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.6, delay: 0.2 }}
                    className="w-full max-w-xl relative group"
                >
                    <div className="absolute -inset-1 bg-gradient-to-r from-primary/50 via-blue-500/50 to-primary/50 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500" />
                    
                    <form onSubmit={handleAnalyze} className="relative bg-black/40 backdrop-blur-xl border border-white/10 rounded-2xl p-2 flex items-center shadow-2xl">
                        <div className="pl-4 text-muted-foreground">
                            <Github className="h-6 w-6" />
                        </div>
                        <Input
                            placeholder="https://github.com/username/repo"
                            className="flex-1 h-14 bg-transparent border-none text-lg focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground/50 font-mono"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            disabled={loading}
                        />
                        <Button
                            type="submit"
                            className="h-12 px-8 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-all duration-300 hover:shadow-[0_0_20px_rgba(var(--primary),0.5)]"
                            disabled={loading}
                        >
                            {loading ? (
                                <Loader2 className="h-5 w-5 animate-spin" />
                            ) : (
                                <ArrowRight className="h-5 w-5" />
                            )}
                        </Button>
                    </form>

                    <AnimatePresence>
                        {error && (
                            <motion.div
                                initial={{ opacity: 0, y: -10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10 }}
                                className="absolute top-full left-0 right-0 mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center backdrop-blur-md"
                            >
                                {error}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.div>

                {/* Features Grid */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.8, delay: 0.4 }}
                    className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-5xl pt-12"
                >
                    {[
                        { icon: ShieldCheck, title: "Security Audit", desc: "Deep scan for vulnerabilities and security risks." },
                        { icon: Zap, title: "Performance Metrics", desc: "Analyze complexity, maintainability, and efficiency." },
                        { icon: Code2, title: "Code Quality", desc: "Automated code review and best practice enforcement." }
                    ].map((feature, idx) => (
                        <div key={idx} className="group p-6 rounded-2xl bg-white/5 border border-white/5 hover:border-primary/20 hover:bg-white/10 transition-all duration-300 backdrop-blur-sm">
                            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
                                <feature.icon className="h-6 w-6 text-primary" />
                            </div>
                            <h3 className="text-lg font-semibold mb-2 text-foreground/90">{feature.title}</h3>
                            <p className="text-sm text-muted-foreground">{feature.desc}</p>
                        </div>
                    ))}
                </motion.div>
            </div>
            
            {/* Footer */}
            <div className="absolute bottom-6 text-xs text-muted-foreground/40 font-mono">
                ENGINE: GEMINI-PRO-3 // STATUS: OPERATIONAL
            </div>
        </main>
    )
}

'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { motion } from 'framer-motion'
import { ArrowRight, Loader2, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function Home() {
    const [url, setUrl] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const router = useRouter()

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

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-6 relative overflow-hidden bg-background">
            {/* Background Ambience */}
            <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
                <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-primary/20 rounded-full blur-[120px] mix-blend-screen animate-pulse" />
                <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-purple-500/10 rounded-full blur-[100px] mix-blend-screen" />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
                className="z-10 w-full max-w-2xl text-center space-y-8"
            >
                <div className="space-y-4">
                    <div className="inline-flex items-center px-3 py-1 rounded-full border border-white/10 bg-white/5 text-xs font-medium text-primary-foreground/80 mb-4">
                        <span className="flex h-2 w-2 rounded-full bg-primary mr-2 animate-pulse"></span>
                        System Online v1.0
                    </div>
                    <h1 className="text-5xl md:text-7xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-b from-white to-white/60">
                        Code MRI
                    </h1>
                    <p className="text-xl text-muted-foreground max-w-lg mx-auto leading-relaxed">
                        Autonomous static analysis & intelligence engine.
                        <br />
                        Scan. Diagnose. Interact.
                    </p>
                </div>

                <form onSubmit={handleAnalyze} className="w-full max-w-md mx-auto space-y-4 pt-8 relative">
                    <div className="relative group">
                        <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-muted-foreground group-focus-within:text-primary transition-colors">
                            <Search className="h-5 w-5" />
                        </div>
                        <Input
                            placeholder="https://github.com/username/repo"
                            className="pl-10 h-14 bg-white/5 border-white/10 text-lg transition-all focus:ring-primary/50 focus:border-primary/50"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    <Button
                        type="submit"
                        className="w-full h-12 text-md font-medium"
                        size="lg"
                        variant="default" // Primary color
                        disabled={loading}
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                Scanning Repository...
                            </>
                        ) : (
                            <>
                                Initialize Scan <ArrowRight className="ml-2 h-4 w-4" />
                            </>
                        )}
                    </Button>

                    {error && (
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-red-400 text-sm mt-3"
                        >
                            {error}
                        </motion.p>
                    )}
                </form>
            </motion.div>

            <footer className="absolute bottom-6 text-xs text-muted-foreground/50">
                Engineered for precision. Secure Execution Environment.
            </footer>
        </main>
    )
}

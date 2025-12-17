import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

interface MarkdownRendererProps {
    content: string;
    className?: string;
}

export function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
    // Ensure content is always a string and handle edge cases
    const safeContent = React.useMemo(() => {
        if (typeof content !== 'string') {
            console.warn('MarkdownRenderer received non-string content:', content);
            return String(content || '');
        }
        return content;
    }, [content]);

    if (!safeContent) {
        return null;
    }

    return (
        <div className={cn("markdown-content text-muted-foreground", className)}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-6 mb-4 text-foreground tracking-tight" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-xl font-semibold mt-5 mb-3 text-foreground/90 tracking-tight" {...props} />,
                    h3: ({node, ...props}) => <h3 className="text-lg font-medium mt-4 mb-2 text-primary" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc list-inside my-3 space-y-1 marker:text-primary/50" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal list-inside my-3 space-y-1 marker:text-primary/50" {...props} />,
                    li: ({node, ...props}) => <li className="text-sm leading-relaxed pl-1" {...props} />,
                    p: ({node, ...props}) => <p className="text-sm leading-7 mb-4 last:mb-0" {...props} />,
                    a: ({node, ...props}) => <a className="text-primary hover:text-primary/80 hover:underline underline-offset-4 transition-colors" target="_blank" rel="noopener noreferrer" {...props} />,
                    blockquote: ({node, ...props}) => <blockquote className="border-l-2 border-primary/30 pl-4 italic text-muted-foreground/80 my-4" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-semibold text-foreground" {...props} />,
                    em: ({node, ...props}) => <em className="italic text-foreground/80" {...props} />,
                    hr: ({node, ...props}) => <hr className="my-6 border-white/10" {...props} />,
                    table: ({node, ...props}) => <div className="overflow-x-auto my-4 rounded-lg border border-white/10"><table className="w-full text-sm text-left" {...props} /></div>,
                    thead: ({node, ...props}) => <thead className="bg-white/5 text-foreground uppercase text-xs font-medium" {...props} />,
                    tbody: ({node, ...props}) => <tbody className="divide-y divide-white/5" {...props} />,
                    tr: ({node, ...props}) => <tr className="hover:bg-white/5 transition-colors" {...props} />,
                    th: ({node, ...props}) => <th className="px-4 py-3 font-medium" {...props} />,
                    td: ({node, ...props}) => <td className="px-4 py-3" {...props} />,
                    code: ({node, className, children, ...props}: any) => {
                        const match = /language-(\w+)/.exec(className || '')
                        const isInline = !match && !String(children).includes('\n')
                        return isInline ? (
                            <code className="bg-primary/10 px-1.5 py-0.5 rounded text-xs font-mono text-primary border border-primary/20" {...props}>
                                {children}
                            </code>
                        ) : (
                            <div className="relative my-4 rounded-lg overflow-hidden bg-[#0D0D12] border border-white/10 shadow-xl">
                                <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/10">
                                    <div className="flex items-center gap-2">
                                        <div className="flex gap-1.5">
                                            <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50" />
                                            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50" />
                                            <div className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/50" />
                                        </div>
                                        <span className="text-xs text-muted-foreground font-mono ml-2">{match?.[1] || 'text'}</span>
                                    </div>
                                </div>
                                <div className="p-4 overflow-x-auto custom-scrollbar">
                                    <code className={cn("text-xs font-mono leading-relaxed", className)} {...props}>
                                        {children}
                                    </code>
                                </div>
                            </div>
                        )
                    }
                }}
            >
                {safeContent}
            </ReactMarkdown>
        </div>
    );
}

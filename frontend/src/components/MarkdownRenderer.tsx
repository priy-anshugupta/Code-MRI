import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
        <div className={`markdown-content ${className}`}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-4 mb-2 text-primary" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-3 mb-2 text-primary/90" {...props} />,
                    h3: ({node, ...props}) => <h3 className="text-lg font-bold mt-3 mb-1 text-primary/80" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc list-inside my-2 space-y-1" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal list-inside my-2 space-y-1" {...props} />,
                    li: ({node, ...props}) => <li className="text-sm leading-relaxed" {...props} />,
                    p: ({node, ...props}) => <p className="text-sm leading-relaxed mb-2 last:mb-0" {...props} />,
                    a: ({node, ...props}) => <a className="text-primary hover:underline" target="_blank" rel="noopener noreferrer" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-bold text-primary-foreground" {...props} />,
                    em: ({node, ...props}) => <em className="italic text-primary-foreground/90" {...props} />,
                    code: ({node, className, children, ...props}: any) => {
                        const match = /language-(\w+)/.exec(className || '')
                        const isInline = !match && !String(children).includes('\n')
                        return isInline ? (
                            <code className="bg-white/10 px-1 py-0.5 rounded text-xs font-mono text-primary-foreground" {...props}>
                                {children}
                            </code>
                        ) : (
                            <div className="relative my-3 rounded-md overflow-hidden bg-black/40 border border-white/10">
                                <div className="flex items-center justify-between px-3 py-1.5 bg-white/5 border-b border-white/10">
                                    <span className="text-xs text-muted-foreground font-mono">{match?.[1] || 'text'}</span>
                                </div>
                                <pre className="p-3 overflow-x-auto text-xs font-mono">
                                    <code className={className} {...props}>
                                        {children}
                                    </code>
                                </pre>
                            </div>
                        )
                    },
                    blockquote: ({node, ...props}) => <blockquote className="border-l-2 border-primary/50 pl-4 italic my-2 text-muted-foreground" {...props} />,
                    table: ({node, ...props}) => <div className="overflow-x-auto my-4"><table className="w-full text-sm text-left border-collapse" {...props} /></div>,
                    th: ({node, ...props}) => <th className="border-b border-white/10 bg-white/5 p-2 font-semibold" {...props} />,
                    td: ({node, ...props}) => <td className="border-b border-white/10 p-2" {...props} />,
                    hr: ({node, ...props}) => <hr className="my-4 border-white/10" {...props} />,
                }}
            >
                {safeContent}
            </ReactMarkdown>
        </div>
    );
}

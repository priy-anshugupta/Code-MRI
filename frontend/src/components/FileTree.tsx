'use client'

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Folder, FileCode, ChevronRight, ChevronDown, File, FileJson, FileType } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FileNode {
    name: string
    type: 'file' | 'folder'
    children?: FileNode[]
    metrics?: any
}

interface FileTreeProps {
    data: FileNode
    onFileSelect?: (filePath: string) => void
    selectedFile?: string | null
}

interface FileTreeItemProps {
    item: FileNode
    depth: number
    currentPath: string
    onFileSelect?: (filePath: string) => void
    selectedFile?: string | null
}

const getFileIcon = (filename: string) => {
    if (filename.endsWith('.tsx') || filename.endsWith('.jsx')) return <FileCode className="h-4 w-4 text-blue-400" />
    if (filename.endsWith('.ts') || filename.endsWith('.js')) return <FileCode className="h-4 w-4 text-yellow-400" />
    if (filename.endsWith('.css') || filename.endsWith('.scss')) return <FileType className="h-4 w-4 text-pink-400" />
    if (filename.endsWith('.json')) return <FileJson className="h-4 w-4 text-green-400" />
    if (filename.endsWith('.py')) return <FileCode className="h-4 w-4 text-blue-500" />
    return <File className="h-4 w-4 text-gray-400" />
}

const FileTreeItem = ({ item, depth = 0, currentPath, onFileSelect, selectedFile }: FileTreeItemProps) => {
    const [isOpen, setIsOpen] = useState(depth === 0)
    const isFolder = item.type === 'folder'
    const fullPath = currentPath ? `${currentPath}/${item.name}` : item.name
    const isSelected = selectedFile === fullPath

    const handleClick = () => {
        if (isFolder) {
            setIsOpen(!isOpen)
        } else if (onFileSelect) {
            onFileSelect(fullPath)
        }
    }

    return (
        <div className="select-none">
            <div
                className={cn(
                    "flex items-center py-1.5 px-2 rounded-md cursor-pointer transition-all duration-200 text-sm group relative",
                    depth > 0 && "ml-3",
                    isSelected 
                        ? "bg-primary/10 text-primary font-medium" 
                        : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                )}
                onClick={handleClick}
            >
                {/* Hover Indicator */}
                <div className={cn(
                    "absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-primary rounded-r transition-all duration-200",
                    isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-50"
                )} />

                <span className="mr-1.5 text-muted-foreground/50 group-hover:text-foreground transition-colors">
                    {isFolder && (
                        <motion.div
                            initial={false}
                            animate={{ rotate: isOpen ? 90 : 0 }}
                            transition={{ duration: 0.2 }}
                        >
                            <ChevronRight className="h-3.5 w-3.5" />
                        </motion.div>
                    )}
                    {!isFolder && <div className="w-3.5" />}
                </span>
                
                <span className="mr-2">
                    {isFolder ? (
                        <Folder className={cn("h-4 w-4 transition-colors", isOpen ? "text-primary/80" : "text-blue-400/60")} />
                    ) : (
                        getFileIcon(item.name)
                    )}
                </span>
                
                <span className="truncate flex-1 font-mono text-xs tracking-tight">{item.name}</span>

                {/* Complexity Badge */}
                {item.metrics && item.metrics.complexity > 10 && (
                    <span className="text-[9px] bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded border border-red-500/20 ml-2">
                        CC {item.metrics.complexity.toFixed(0)}
                    </span>
                )}
            </div>

            <AnimatePresence>
                {isFolder && isOpen && item.children && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2, ease: "easeInOut" }}
                        className="overflow-hidden border-l border-white/5 ml-[1.1rem]"
                    >
                        {item.children.map((child, idx) => (
                            <FileTreeItem 
                                key={idx} 
                                item={child} 
                                depth={depth + 1} 
                                currentPath={fullPath}
                                onFileSelect={onFileSelect}
                                selectedFile={selectedFile}
                            />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

export const FileTree = ({ data, onFileSelect, selectedFile }: FileTreeProps) => {
    if (!data) return null;
    return (
        <div className="w-full">
            <FileTreeItem 
                item={data} 
                depth={0} 
                currentPath="" 
                onFileSelect={onFileSelect}
                selectedFile={selectedFile}
            />
        </div>
    )
}

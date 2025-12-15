'use client'

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Folder, FileCode, ChevronRight, ChevronDown, File } from 'lucide-react'
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

const FileTreeItem = ({ item, depth = 0, currentPath, onFileSelect, selectedFile }: FileTreeItemProps) => {
    const [isOpen, setIsOpen] = useState(depth === 0)
    const isFolder = item.type === 'folder'
    const fullPath = currentPath ? `${currentPath}/${item.name}` : item.name
    const isSelected = selectedFile === fullPath

    // Icon selection
    const Icon = isFolder ? Folder : (item.name.endsWith('.py') || item.name.endsWith('.js') || item.name.endsWith('.ts') || item.name.endsWith('.tsx') || item.name.endsWith('.jsx') ? FileCode : File)

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
                    "flex items-center py-1.5 px-2 hover:bg-white/5 rounded-md cursor-pointer transition-colors text-sm text-foreground/80 hover:text-foreground group",
                    depth > 0 && "ml-4",
                    isSelected && "bg-primary/20 text-primary border-l-2 border-primary"
                )}
                onClick={handleClick}
            >
                <span className="mr-2 text-muted-foreground group-hover:text-primary transition-colors">
                    {isFolder && (
                        isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />
                    )}
                    {!isFolder && <div className="w-3.5" />} {/* Spacer */}
                </span>
                <Icon className={cn("h-4 w-4 mr-2", isFolder ? "text-blue-400/80" : "text-gray-400", isSelected && "text-primary")} />
                <span className="truncate flex-1">{item.name}</span>

                {/* Simple Metric Badge if available */}
                {item.metrics && item.metrics.complexity > 5 && (
                    <span className="text-[10px] bg-red-500/20 text-red-300 px-1.5 rounded ml-2">
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
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden border-l border-white/5 ml-3"
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
        <div className="w-full overflow-x-auto p-4">
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

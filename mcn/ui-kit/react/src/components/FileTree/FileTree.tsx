import * as React from 'react'
import { ChevronRight, ChevronDown, File, Folder, FolderOpen } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface FileTreeNode {
  /** Unique identifier */
  id: string
  /** Display name */
  name: string
  /** Type of node */
  type: 'file' | 'folder'
  /** Children (only for folders) */
  children?: FileTreeNode[]
  /** Custom icon emoji or React node */
  icon?: React.ReactNode
  /** Mark as modified */
  modified?: boolean
}

export interface FileTreeProps {
  /** Tree data */
  nodes: FileTreeNode[]
  /** Currently selected node id */
  selectedId?: string
  /** Called when a node is clicked */
  onSelect?: (node: FileTreeNode) => void
  /** Initially expanded folder ids */
  defaultExpanded?: string[]
  /** className for container */
  className?: string
}

function TreeNode({
  node,
  depth,
  selectedId,
  onSelect,
  expanded,
  onToggle,
}: {
  node: FileTreeNode
  depth: number
  selectedId?: string
  onSelect?: (n: FileTreeNode) => void
  expanded: Set<string>
  onToggle: (id: string) => void
}) {
  const isFolder = node.type === 'folder'
  const isExpanded = expanded.has(node.id)
  const isSelected = node.id === selectedId

  const handleClick = () => {
    if (isFolder) onToggle(node.id)
    onSelect?.(node)
  }

  const Icon = node.icon ? (
    <span className="text-[13px]">{node.icon}</span>
  ) : isFolder ? (
    isExpanded ? <FolderOpen size={13} className="text-[#ca8a04]" /> : <Folder size={13} className="text-[#ca8a04]" />
  ) : (
    <File size={13} className="text-[#71717a]" />
  )

  return (
    <>
      <div
        className={cn(
          'flex items-center gap-1.5 py-[3px] pr-2 rounded-md cursor-pointer select-none',
          'text-[12.5px] text-[#09090b]',
          'hover:bg-[#f4f4f5] transition-colors duration-[0.1s]',
          isSelected && 'bg-[rgba(59,130,246,0.08)] text-[#3b82f6] font-medium'
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={handleClick}
      >
        {isFolder && (
          <span className="text-[#71717a] w-3 flex-shrink-0">
            {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </span>
        )}
        {!isFolder && <span className="w-3 flex-shrink-0" />}
        <span className="flex-shrink-0">{Icon}</span>
        <span className="truncate">{node.name}</span>
        {node.modified && (
          <span className="ml-auto text-[#3b82f6] text-[10px] font-bold">●</span>
        )}
      </div>
      {isFolder && isExpanded && node.children?.map((child) => (
        <TreeNode
          key={child.id}
          node={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
          expanded={expanded}
          onToggle={onToggle}
        />
      ))}
    </>
  )
}

/**
 * MCN FileTree — VS Code-style collapsible file tree.
 *
 * @example
 * <FileTree
 *   nodes={[{ id: '1', name: 'src', type: 'folder', children: [{ id: '2', name: 'main.mcn', type: 'file' }] }]}
 *   onSelect={(node) => openFile(node.id)}
 * />
 */
export function FileTree({ nodes, selectedId, onSelect, defaultExpanded = [], className }: FileTreeProps) {
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set(defaultExpanded))

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className={cn('py-1 select-none', className)}>
      {nodes.map((node) => (
        <TreeNode
          key={node.id}
          node={node}
          depth={0}
          selectedId={selectedId}
          onSelect={onSelect}
          expanded={expanded}
          onToggle={toggle}
        />
      ))}
    </div>
  )
}

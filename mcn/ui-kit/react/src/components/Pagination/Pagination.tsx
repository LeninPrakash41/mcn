import * as React from 'react'
import { ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react'
import { cn } from '../../lib/utils'
import { Button } from '../Button/Button'

export interface PaginationProps {
  /** Current page (1-indexed) */
  page: number
  /** Total number of pages */
  totalPages: number
  /** Called when page changes */
  onPageChange: (page: number) => void
  /** Number of sibling pages to show around current */
  siblings?: number
  /** Show first/last page buttons */
  showEdges?: boolean
  /** className */
  className?: string
}

function getRange(start: number, end: number): number[] {
  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
}

/**
 * MCN Pagination — page navigation with ellipsis for large page counts.
 *
 * @example
 * <Pagination page={currentPage} totalPages={20} onPageChange={setPage} />
 */
export function Pagination({ page, totalPages, onPageChange, siblings = 1, showEdges = true, className }: PaginationProps) {
  const pages = React.useMemo(() => {
    const total = 5 + siblings * 2
    if (totalPages <= total) return getRange(1, totalPages)

    const leftSibling = Math.max(page - siblings, 1)
    const rightSibling = Math.min(page + siblings, totalPages)

    const showLeft = leftSibling > 2
    const showRight = rightSibling < totalPages - 1

    if (!showLeft && showRight) return [...getRange(1, 3 + siblings * 2), '...', totalPages]
    if (showLeft && !showRight) return [1, '...', ...getRange(totalPages - (3 + siblings * 2 - 1), totalPages)]
    return [1, '...', ...getRange(leftSibling, rightSibling), '...', totalPages]
  }, [page, totalPages, siblings])

  return (
    <nav className={cn('flex items-center gap-1', className)} aria-label="Pagination">
      <Button
        variant="outline"
        size="icon-sm"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"
      >
        <ChevronLeft size={14} />
      </Button>

      {pages.map((p, i) =>
        p === '...' ? (
          <span key={`ellipsis-${i}`} className="px-2 text-[#71717a]">
            <MoreHorizontal size={14} />
          </span>
        ) : (
          <Button
            key={p}
            variant={p === page ? 'primary' : 'ghost'}
            size="icon-sm"
            onClick={() => onPageChange(p as number)}
            aria-current={p === page ? 'page' : undefined}
            aria-label={`Page ${p}`}
          >
            {p}
          </Button>
        )
      )}

      <Button
        variant="outline"
        size="icon-sm"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        aria-label="Next page"
      >
        <ChevronRight size={14} />
      </Button>
    </nav>
  )
}

import * as React from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { cn } from '../../lib/utils'
import { Spinner } from '../Spinner/Spinner'

export interface TableColumn<T = Record<string, unknown>> {
  /** Data key */
  key: keyof T | string
  /** Column header label */
  header: string
  /** Custom render function */
  render?: (value: unknown, row: T, index: number) => React.ReactNode
  /** Enable sorting for this column */
  sortable?: boolean
  /** Column width */
  width?: string | number
  /** Text alignment */
  align?: 'left' | 'center' | 'right'
}

export interface TableProps<T = Record<string, unknown>> {
  /** Column definitions */
  columns: TableColumn<T>[]
  /** Row data */
  data: T[]
  /** Row key field or function */
  rowKey?: keyof T | ((row: T, i: number) => string | number)
  /** Loading state */
  isLoading?: boolean
  /** Empty state message */
  emptyMessage?: string
  /** Enable row hover highlight */
  hoverable?: boolean
  /** Row click handler */
  onRowClick?: (row: T, index: number) => void
  /** Table class */
  className?: string
}

type SortDir = 'asc' | 'desc' | null

/**
 * MCN Table — data table with optional column sorting.
 *
 * @example
 * <Table
 *   columns={[{ key: 'name', header: 'Name', sortable: true }, { key: 'status', header: 'Status', render: (v) => <Badge>{v}</Badge> }]}
 *   data={users}
 *   rowKey="id"
 * />
 */
export function Table<T = Record<string, unknown>>({
  columns,
  data,
  rowKey,
  isLoading,
  emptyMessage = 'No data',
  hoverable = true,
  onRowClick,
  className,
}: TableProps<T>) {
  const [sortKey, setSortKey] = React.useState<string | null>(null)
  const [sortDir, setSortDir] = React.useState<SortDir>(null)

  const handleSort = (key: string) => {
    if (sortKey !== key) { setSortKey(key); setSortDir('asc') }
    else if (sortDir === 'asc') setSortDir('desc')
    else { setSortKey(null); setSortDir(null) }
  }

  const sortedData = React.useMemo(() => {
    if (!sortKey || !sortDir) return data
    return [...data].sort((a, b) => {
      const av = (a as Record<string, unknown>)[sortKey]
      const bv = (b as Record<string, unknown>)[sortKey]
      const cmp = av == null ? -1 : bv == null ? 1 : av < bv ? -1 : av > bv ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir])

  const getKey = (row: T, i: number): React.Key => {
    if (!rowKey) return i
    if (typeof rowKey === 'function') return rowKey(row, i)
    return (row as Record<string, unknown>)[rowKey as string] as React.Key ?? i
  }

  return (
    <div className={cn('w-full overflow-auto rounded-lg border border-[#e4e4e7]', className)}>
      <table className="w-full text-[13px] border-collapse">
        <thead className="bg-[#f4f4f5]">
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                style={{ width: col.width }}
                className={cn(
                  'px-3 py-2.5 text-left font-semibold text-[#09090b] border-b border-[#e4e4e7]',
                  'whitespace-nowrap',
                  col.align === 'center' && 'text-center',
                  col.align === 'right' && 'text-right',
                  col.sortable && 'cursor-pointer select-none hover:bg-[#e4e4e7] transition-colors'
                )}
                onClick={col.sortable ? () => handleSort(String(col.key)) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && (
                    sortKey === String(col.key) ? (
                      sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
                    ) : (
                      <ChevronsUpDown size={12} className="opacity-30" />
                    )
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <tr>
              <td colSpan={columns.length} className="py-10 text-center">
                <Spinner className="mx-auto" />
              </td>
            </tr>
          ) : sortedData.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="py-10 text-center text-[#71717a]">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            sortedData.map((row, i) => (
              <tr
                key={getKey(row, i)}
                className={cn(
                  'border-b border-[#f4f4f5] last:border-0',
                  hoverable && 'hover:bg-[#f9f9fb] transition-colors',
                  onRowClick && 'cursor-pointer'
                )}
                onClick={() => onRowClick?.(row, i)}
              >
                {columns.map((col) => {
                  const val = (row as Record<string, unknown>)[String(col.key)]
                  return (
                    <td
                      key={String(col.key)}
                      className={cn(
                        'px-3 py-2.5 text-[#09090b]',
                        col.align === 'center' && 'text-center',
                        col.align === 'right' && 'text-right'
                      )}
                    >
                      {col.render ? col.render(val, row, i) : String(val ?? '')}
                    </td>
                  )
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

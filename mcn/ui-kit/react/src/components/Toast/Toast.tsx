import * as React from 'react'
import * as ToastPrimitive from '@radix-ui/react-toast'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import { cn } from '../../lib/utils'

export type ToastVariant = 'default' | 'success' | 'error' | 'warning' | 'info'

export interface ToastData {
  id: string
  title: string
  description?: string
  variant?: ToastVariant
  duration?: number
  action?: { label: string; onClick: () => void }
}

interface ToastContextValue {
  toasts: ToastData[]
  toast: (data: Omit<ToastData, 'id'>) => void
  dismiss: (id: string) => void
}

const ToastContext = React.createContext<ToastContextValue | null>(null)

/** Access the toast API from anywhere inside ToastProvider */
export function useToast() {
  const ctx = React.useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}

const variantConfig = {
  default: { icon: null, bg: 'bg-white', text: 'text-[#09090b]', border: 'border-[#e4e4e7]' },
  success: { icon: <CheckCircle size={16} className="text-[#16a34a]" />, bg: 'bg-white', text: 'text-[#09090b]', border: 'border-[#16a34a]/30' },
  error:   { icon: <AlertCircle size={16} className="text-[#dc2626]" />, bg: 'bg-white', text: 'text-[#09090b]', border: 'border-[#dc2626]/30' },
  warning: { icon: <AlertTriangle size={16} className="text-[#ca8a04]" />, bg: 'bg-white', text: 'text-[#09090b]', border: 'border-[#ca8a04]/30' },
  info:    { icon: <Info size={16} className="text-[#3b82f6]" />, bg: 'bg-white', text: 'text-[#09090b]', border: 'border-[#3b82f6]/30' },
}

/**
 * Wraps your app to enable toasts. Place at the root.
 *
 * @example
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastData[]>([])

  const toast = React.useCallback((data: Omit<ToastData, 'id'>) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((prev) => [...prev, { ...data, id }])
  }, [])

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}

        {toasts.map((t) => {
          const cfg = variantConfig[t.variant ?? 'default']
          return (
            <ToastPrimitive.Root
              key={t.id}
              duration={t.duration ?? 4000}
              onOpenChange={(open) => { if (!open) dismiss(t.id) }}
              className={cn(
                'group pointer-events-auto relative flex w-full items-start gap-3 rounded-xl border p-4 shadow-lg',
                'max-w-[380px] transition-all',
                'data-[state=open]:animate-in data-[state=closed]:animate-out',
                'data-[swipe=end]:animate-out data-[state=closed]:fade-out-80',
                'data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full',
                'data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)]',
                'data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none',
                cfg.bg, cfg.border
              )}
            >
              {cfg.icon && <span className="mt-0.5 flex-shrink-0">{cfg.icon}</span>}
              <div className="flex-1 min-w-0">
                <ToastPrimitive.Title className={cn('text-[13px] font-semibold', cfg.text)}>
                  {t.title}
                </ToastPrimitive.Title>
                {t.description && (
                  <ToastPrimitive.Description className="mt-0.5 text-[12px] text-[#71717a]">
                    {t.description}
                  </ToastPrimitive.Description>
                )}
                {t.action && (
                  <ToastPrimitive.Action
                    altText={t.action.label}
                    onClick={t.action.onClick}
                    className="mt-2 text-[12px] font-medium text-[#3b82f6] hover:underline"
                  >
                    {t.action.label}
                  </ToastPrimitive.Action>
                )}
              </div>
              <ToastPrimitive.Close
                onClick={() => dismiss(t.id)}
                className="flex-shrink-0 text-[#71717a] hover:text-[#09090b] transition-colors"
              >
                <X size={14} />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          )
        })}

        <ToastPrimitive.Viewport className="fixed bottom-4 right-4 z-[100] flex max-h-screen flex-col-reverse gap-2 p-4 sm:right-4 sm:flex-col md:max-w-[420px]" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}

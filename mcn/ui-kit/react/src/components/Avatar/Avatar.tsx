import * as React from 'react'
import { cn } from '../../lib/utils'
import { User } from 'lucide-react'

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Image source URL */
  src?: string
  /** Alt text for the image */
  alt?: string
  /** Fallback initials (up to 2 chars) */
  initials?: string
  /** Avatar size */
  size?: 'sm' | 'md' | 'lg' | 'xl'
  /** Online status indicator */
  status?: 'online' | 'offline' | 'busy' | 'away'
}

const sizeMap = {
  sm: 'h-7 w-7 text-[11px]',
  md: 'h-9 w-9 text-[13px]',
  lg: 'h-12 w-12 text-[15px]',
  xl: 'h-16 w-16 text-xl',
}

const statusColorMap = {
  online:  'bg-[#16a34a]',
  offline: 'bg-[#a1a1aa]',
  busy:    'bg-[#dc2626]',
  away:    'bg-[#ca8a04]',
}

/**
 * MCN Avatar — user avatar with image, initials fallback, and status indicator.
 *
 * @example
 * <Avatar src="/user.png" alt="John Doe" status="online" />
 * <Avatar initials="JD" size="lg" />
 */
export function Avatar({ src, alt, initials, size = 'md', status, className, ...props }: AvatarProps) {
  const [imgError, setImgError] = React.useState(false)
  const showFallback = !src || imgError

  return (
    <div className={cn('relative inline-flex flex-shrink-0', className)} {...props}>
      <div
        className={cn(
          'rounded-full overflow-hidden flex items-center justify-center',
          'bg-[#e4e4e7] text-[#71717a] font-medium select-none',
          sizeMap[size]
        )}
      >
        {!showFallback ? (
          <img
            src={src}
            alt={alt}
            className="h-full w-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : initials ? (
          <span>{initials.slice(0, 2).toUpperCase()}</span>
        ) : (
          <User size={size === 'sm' ? 12 : size === 'xl' ? 24 : 16} />
        )}
      </div>
      {status && (
        <span
          className={cn(
            'absolute bottom-0 right-0 block rounded-full ring-2 ring-white',
            statusColorMap[status],
            size === 'sm' ? 'h-2 w-2' : size === 'xl' ? 'h-3.5 w-3.5' : 'h-2.5 w-2.5'
          )}
        />
      )}
    </div>
  )
}

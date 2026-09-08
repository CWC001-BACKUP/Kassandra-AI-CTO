import { Link } from 'react-router-dom'

interface LogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showText?: boolean
  linkTo?: string
  className?: string
}

const sizes = {
  sm: { img: 'h-8 w-8', text: 'text-base' },
  md: { img: 'h-10 w-10', text: 'text-lg' },
  lg: { img: 'h-14 w-14', text: 'text-xl' },
  xl: { img: 'h-20 w-20', text: 'text-3xl' },
}

export function Logo({
  size = 'md',
  showText = true,
  linkTo,
  className = '',
}: LogoProps) {
  const s = sizes[size]

  const content = (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className={`relative ${s.img} shrink-0`}>
        <div className="absolute inset-0 rounded-xl bg-[var(--color-cyan)]/20 blur-lg" />
        <img
          src="/logo.png"
          alt="Kassandra"
          className={`relative ${s.img} object-contain drop-shadow-[0_0_12px_rgba(0,210,255,0.4)]`}
        />
      </div>
      {showText && (
        <span
          className={`${s.text} font-display font-bold tracking-tight gradient-text`}
        >
          Kassandra
        </span>
      )}
    </div>
  )

  if (linkTo) {
    return (
      <Link to={linkTo} className="transition-opacity hover:opacity-85">
        {content}
      </Link>
    )
  }

  return content
}

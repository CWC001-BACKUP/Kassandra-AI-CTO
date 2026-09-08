import { Logo } from '../ui/Logo'

const footerLinks = {
  Product: [
    { label: 'Features', href: '#features' },
    { label: 'How It Works', href: '#how-it-works' },
    { label: 'Pricing', href: '#pricing' },
    { label: 'Changelog', href: '#' },
  ],
  Company: [
    { label: 'About', href: '#' },
    { label: 'Blog', href: '#' },
    { label: 'Careers', href: '#' },
    { label: 'Contact', href: '#' },
  ],
  Legal: [
    { label: 'Privacy', href: '#' },
    { label: 'Terms', href: '#' },
    { label: 'Security', href: '#' },
  ],
}

export function Footer() {
  return (
    <footer className="relative border-t border-[var(--color-border-subtle)] bg-[var(--color-surface)]">
      <div className="pointer-events-none absolute inset-0 grid-pattern opacity-30" />
      <div className="relative mx-auto max-w-7xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Logo size="md" linkTo="/" />
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-[var(--color-text-muted)]">
              Kassandra is your AI-powered code manager — persistent institutional
              memory, intelligent change tracking, and engineering insights for
              modern teams.
            </p>
            <div className="mt-6 flex gap-3">
              {['GitHub', 'Twitter', 'Discord'].map((social) => (
                <a
                  key={social}
                  href="#"
                  className="btn-glass btn-glass-sm"
                >
                  {social}
                </a>
              ))}
            </div>
          </div>

          {Object.entries(footerLinks).map(([title, links]) => (
            <div key={title}>
              <h3 className="font-display text-sm font-semibold text-[var(--color-highlight)]">
                {title}
              </h3>
              <ul className="mt-4 space-y-3">
                {links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-cyan)]"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-[var(--color-border-subtle)] pt-8 sm:flex-row">
          <p className="text-xs text-[var(--color-text-dim)]">
            &copy; {new Date().getFullYear()} Kassandra. All rights reserved.
          </p>
          <p className="text-xs text-[var(--color-text-dim)]">
            Built with{' '}
            <span className="gradient-text font-medium">neural memory</span>{' '}
            for engineering teams.
          </p>
        </div>
      </div>
    </footer>
  )
}

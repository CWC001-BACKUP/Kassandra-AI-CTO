import type { EvidenceRef } from '../../types'

const SOURCE_STYLES: Record<string, string> = {
  github: 'text-[var(--color-text-dim)]',
  sibyl: 'text-[var(--color-purple)]',
  session: 'text-[var(--color-text-muted)]',
}

const SOURCE_LABELS: Record<string, string> = {
  github: 'GitHub',
  sibyl: 'Sibyl',
  session: 'Session',
}

function normalizeEvidence(items: EvidenceRef[] | string[] | undefined): EvidenceRef[] {
  if (!items?.length) return []
  return items.map((item) =>
    typeof item === 'string'
      ? { label: item, source: 'github' as const }
      : item
  )
}

export function EvidenceList({ evidence }: { evidence?: EvidenceRef[] | string[] }) {
  const items = normalizeEvidence(evidence)
  if (!items.length) return null

  return (
    <div className="mt-3 border-t border-[var(--color-border-subtle)] pt-2">
      <p className="text-[10px] uppercase tracking-wide text-[var(--color-text-dim)]">
        Evidence
      </p>
      <ul className="mt-1 space-y-1 text-xs">
        {items.map((item, index) => {
          const source = item.source || 'github'
          const sourceClass = SOURCE_STYLES[source] || SOURCE_STYLES.github
          const content = (
            <>
              <span className="mr-1.5 rounded px-1 py-0.5 text-[9px] uppercase tracking-wide opacity-80">
                {SOURCE_LABELS[source] || source}
              </span>
              <span className={sourceClass}>{item.label}</span>
            </>
          )
          return (
            <li key={`${item.label}-${index}`}>
              {item.url ? (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex flex-wrap items-baseline gap-1 transition-colors hover:text-[var(--color-cyan)]"
                >
                  {content}
                </a>
              ) : (
                <span className="inline-flex flex-wrap items-baseline gap-1">{content}</span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

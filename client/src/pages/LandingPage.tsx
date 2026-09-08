import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { SectionHeader } from '../components/ui/SectionHeader'
import { GradientText } from '../components/ui/GradientText'
import { FeatureIcon } from '../components/ui/FeatureIcon'
import { LazyScene } from '../components/three/LazyScene'
import { HeroGeometry } from '../components/three/HeroGeometry'
import { useAuth } from '../context/AuthProvider'

const features = [
  {
    title: 'Persistent Memory',
    description:
      'Kassandra remembers every architectural decision, incident, and rejected approach — so your team never loses institutional knowledge.',
    icon: 'memory' as const,
    gradient: 'from-[var(--color-cyan)] to-[var(--color-blue)]',
  },
  {
    title: 'AI CTO Chat',
    description:
      'Ask engineering questions grounded in your project history. Get context-aware answers backed by real code changes and team decisions.',
    icon: 'chat' as const,
    gradient: 'from-[var(--color-blue)] to-[var(--color-purple)]',
  },
  {
    title: 'Change Tracking',
    description:
      'Automatically track PRs, commits, and code changes. Understand what changed, why, and who was involved — in real time.',
    icon: 'changes' as const,
    gradient: 'from-[var(--color-purple)] to-[var(--color-magenta)]',
  },
  {
    title: 'Smart Reports',
    description:
      'Generate engineering reports, sprint summaries, and incident post-mortems with one click. Export to PDF or share with stakeholders.',
    icon: 'reports' as const,
    gradient: 'from-[var(--color-cyan)] to-[var(--color-magenta)]',
  },
  {
    title: 'GitHub Integration',
    description:
      'Connect your repositories in seconds. Kassandra syncs with GitHub to build a living map of your codebase and team activity.',
    icon: 'github' as const,
    gradient: 'from-[var(--color-blue-deep)] to-[var(--color-cyan)]',
  },
  {
    title: 'Log Intelligence',
    description:
      'Centralized log exploration with AI-powered anomaly detection. Spot issues before they become incidents.',
    icon: 'logs' as const,
    gradient: 'from-[var(--color-purple-deep)] to-[var(--color-cyan-bright)]',
  },
]

const steps = [
  {
    step: '01',
    title: 'Connect Your Repo',
    description: 'Link your GitHub repository with one click. Kassandra indexes your codebase and commit history.',
  },
  {
    step: '02',
    title: 'Build Memory',
    description: 'As your team works, Kassandra learns — capturing decisions, patterns, and context automatically.',
  },
  {
    step: '03',
    title: 'Ask Anything',
    description: 'Chat with your AI CTO. Get answers grounded in your actual project history, not generic advice.',
  },
]

const stats = [
  { value: '10x', label: 'Faster onboarding' },
  { value: '85%', label: 'Less context switching' },
  { value: '24/7', label: 'Institutional memory' },
  { value: '∞', label: 'Decisions remembered' },
]

export function LandingPage() {
  const { isAuthenticated } = useAuth()

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-20 lg:py-28">
        <div className="relative mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-2 lg:gap-16">
          <div className="flex flex-col items-center text-center lg:items-start lg:text-left">
            <div className="animate-fade-up opacity-0">
              <Badge variant="cyan" dot>
                Now in early access
              </Badge>
            </div>

            <h1 className="mt-6 max-w-2xl animate-fade-up stagger-1 text-4xl font-bold leading-[1.1] tracking-tight opacity-0 lg:text-6xl">
              Your codebase has a{' '}
              <GradientText>memory</GradientText>
            </h1>

            <p className="mt-6 max-w-xl animate-fade-up stagger-2 text-lg leading-relaxed text-[var(--color-text-muted)] opacity-0">
              Kassandra is the AI-powered code manager that gives your engineering
              team persistent institutional memory — so nothing gets lost between
              sprints, rotations, or rewrites.
            </p>

            <div className="mt-10 flex animate-fade-up stagger-3 flex-wrap items-center justify-center gap-4 opacity-0 lg:justify-start">
              {isAuthenticated ? (
                <Link to="/dashboard">
                  <Button size="lg">Go to Dashboard</Button>
                </Link>
              ) : (
                <Link to="/signup">
                  <Button size="lg">Start Free Trial</Button>
                </Link>
              )}
              <Link to={isAuthenticated ? '/dashboard/chat' : '/login'}>
                <Button variant="outline" size="lg">
                  {isAuthenticated ? 'Open AI Chat' : 'View Demo'}
                </Button>
              </Link>
            </div>

            <div className="mt-12 flex animate-fade-up stagger-4 flex-wrap items-center justify-center gap-6 opacity-0 lg:justify-start">
              {['WebGL-powered', 'GitHub native', 'SOC 2 ready'].map((tag) => (
                <span
                  key={tag}
                  className="flex items-center gap-2 text-xs font-medium text-[var(--color-text-dim)]"
                >
                  <span className="h-1 w-1 rounded-full bg-[var(--color-cyan)]" />
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <div className="relative flex h-[320px] items-center justify-center lg:h-[480px]">
            <div className="absolute inset-0 rounded-2xl border border-[var(--color-border-subtle)] bg-[var(--color-surface)]/30 backdrop-blur-sm" />
            <LazyScene
              className="absolute inset-0 rounded-2xl"
              camera={{ position: [0, 0, 5], fov: 45 }}
              disableOnMobile
            >
              <HeroGeometry />
            </LazyScene>
            <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-[var(--color-cyan)]/10" />
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-[var(--color-border-subtle)] bg-[var(--color-surface)]/50 px-6 py-14 backdrop-blur-sm">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-8 md:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="text-center">
              <p className="font-display text-3xl font-bold gradient-text lg:text-4xl">
                {stat.value}
              </p>
              <p className="mt-1.5 text-sm text-[var(--color-text-muted)]">
                {stat.label}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="px-6 py-24">
        <div className="mx-auto max-w-7xl">
          <SectionHeader
            badge="Capabilities"
            title="Everything your team needs"
            description="Built for engineering teams who are tired of repeating themselves."
          />

          <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <Card key={feature.title} interactive className="group p-6">
                <div
                  className={`mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${feature.gradient} shadow-lg transition-transform duration-300 group-hover:scale-110`}
                >
                  <FeatureIcon name={feature.icon} />
                </div>
                <h3 className="font-display text-lg font-semibold">{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-muted)]">
                  {feature.description}
                </p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="border-t border-[var(--color-border-subtle)] bg-[var(--color-surface)]/40 px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <SectionHeader
            badge="Workflow"
            title="How it works"
            description="Three steps to never lose context again."
          />

          <div className="relative mt-16 grid gap-8 md:grid-cols-3">
            <div className="pointer-events-none absolute top-12 hidden h-px w-full bg-gradient-to-r from-transparent via-[var(--color-cyan)]/30 to-transparent md:block" />
            {steps.map((step) => (
              <div key={step.step} className="relative text-center">
                <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--color-cyan)]/20 bg-[var(--color-cyan-muted)] font-display text-lg font-bold text-[var(--color-cyan)]">
                  {step.step}
                </div>
                <h3 className="font-display text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-muted)]">
                  {step.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="px-6 py-24">
        <div className="mx-auto max-w-3xl">
          <SectionHeader
            badge="Pricing"
            title="Simple, transparent pricing"
            description="Start free. Scale as your team grows."
          />

          <Card glow className="mt-12 p-8 lg:p-10">
            <div className="flex items-center justify-between">
              <Badge variant="cyan">Early Access</Badge>
              <span className="text-xs text-[var(--color-text-dim)]">No credit card required</span>
            </div>
            <p className="mt-6">
              <span className="font-display text-5xl font-bold">$0</span>
              <span className="text-[var(--color-text-muted)]"> / month</span>
            </p>
            <ul className="mt-8 space-y-3.5 text-left text-sm text-[var(--color-text-muted)]">
              {[
                'Unlimited repositories',
                'AI CTO chat',
                'Change tracking & logs',
                'Report generation',
                'GitHub integration',
              ].map((item) => (
                <li key={item} className="flex items-center gap-3">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-cyan-muted)]">
                    <svg className="h-3 w-3 text-[var(--color-cyan)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </span>
                  {item}
                </li>
              ))}
            </ul>
            <Link to="/signup" className="mt-8 block">
              <Button fullWidth size="lg">
                Get Started Free
              </Button>
            </Link>
          </Card>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--color-border-subtle)] bg-[var(--color-surface)]/40 px-6 py-24">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="font-display text-3xl font-bold lg:text-4xl">
            Ready to give your codebase a{' '}
            <GradientText>memory</GradientText>?
          </h2>
          <p className="mt-4 text-[var(--color-text-muted)]">
            Join engineering teams who never lose context again.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link to="/signup">
              <Button size="lg">Create Account</Button>
            </Link>
            <Link to="/login">
              <Button variant="secondary" size="lg">
                Sign in with GitHub
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}

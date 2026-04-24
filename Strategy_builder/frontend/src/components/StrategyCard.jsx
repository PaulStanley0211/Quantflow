export default function StrategyCard({ rules }) {
  if (!rules) return null

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  })

  const tags = [
    rules.strategy_type      && { label: rules.strategy_type,                               color: 'var(--amber)'     },
    rules.direction          && { label: rules.direction,                                   color: 'var(--signal-up)' },
    rules.holding_period     && { label: `${rules.holding_period}d hold`,                   color: 'var(--ink-dim)'   },
    rules.risk_per_trade_pct && { label: `${rules.risk_per_trade_pct}% risk / trade`,       color: 'var(--signal-cool)' },
  ].filter(Boolean)

  return (
    <article
      className="rise-1"
      style={{
        borderTop:    '1px solid var(--rule-bright)',
        borderBottom: '1px solid var(--rule)',
        padding: '28px 0 32px',
        marginBottom: 8,
      }}
    >
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
        <div className="label" style={{ color: 'var(--amber)' }}>Dispatch</div>
        <div style={{ flex: 1, height: 1, background: 'var(--rule)' }} />
        <div className="label" style={{ color: 'var(--ink-muted)' }}>{today}</div>
      </div>

      <h1 className="display" style={{
        fontSize: 'clamp(36px, 5vw, 64px)', marginBottom: 16, maxWidth: 900,
      }}>
        {rules.strategy_name || 'Custom Strategy'}
      </h1>

      <p style={{
        fontFamily: 'var(--serif)', fontSize: 17, fontWeight: 400,
        color: 'var(--ink-dim)', lineHeight: 1.5, maxWidth: 760,
        fontVariationSettings: '"opsz" 48',
        marginBottom: 18,
      }}>
        {rules.description}
      </p>

      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center' }}>
        {tags.map((t, i) => (
          <div key={t.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 6, height: 6, background: t.color }} />
            <span style={{
              fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.14em',
              color: 'var(--ink-dim)', fontWeight: 500,
            }}>{t.label}</span>
            {i < tags.length - 1 && <div style={{ width: 1, height: 14, background: 'var(--rule)', marginLeft: 10 }} />}
          </div>
        ))}
      </div>
    </article>
  )
}

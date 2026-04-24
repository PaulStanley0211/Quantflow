export default function EmptyState() {
  return (
    <div style={{
      height: '100%', minHeight: 500,
      display: 'flex', flexDirection: 'column',
      alignItems: 'flex-start', justifyContent: 'center',
      padding: '40px 0',
      animation: 'paper-rise .6s ease both',
    }}>
      {/* Masthead */}
      <div className="label" style={{ color: 'var(--amber)', marginBottom: 14 }}>Vol. I &nbsp;·&nbsp; Strategy Lab</div>

      <h1 className="display" style={{
        fontSize: 'clamp(54px, 7vw, 96px)',
        marginBottom: 22, maxWidth: 900,
      }}>
        Trade ideas, <em>backtested</em><br />
        across fifty-four<br />
        <em style={{ color: 'var(--amber)' }}>instruments.</em>
      </h1>

      <div style={{
        fontSize: 15, color: 'var(--ink-dim)', lineHeight: 1.6,
        maxWidth: 540, marginBottom: 30,
      }}>
        Write your strategy in plain English. The parser converts it into executable
        rules and runs it against two years of daily data on every DAX constituent,
        German index, major cryptocurrency, and primary commodity.
      </div>

      <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
        {[
          { n: '40', l: 'DAX Stocks' },
          { n: '04', l: 'Indexes' },
          { n: '05', l: 'Crypto' },
          { n: '05', l: 'Commodities' },
          { n: '2Y', l: 'Lookback' },
        ].map(({ n, l }) => (
          <div key={l} style={{ borderLeft: '1px solid var(--rule-bright)', paddingLeft: 14 }}>
            <div className="numeric" style={{ fontSize: 30, color: 'var(--ink)', lineHeight: 1, marginBottom: 4, fontWeight: 500 }}>{n}</div>
            <div className="label">{l}</div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 48, fontSize: 12, color: 'var(--ink-muted)', fontStyle: 'italic', fontFamily: 'var(--serif)' }}>
        Begin by describing a strategy in the margin, left →
      </div>
    </div>
  )
}

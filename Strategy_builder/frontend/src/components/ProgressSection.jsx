export default function ProgressSection({ progress, liveRows }) {
  if (!progress && liveRows.length === 0) return null

  const pct = progress ? (progress.current / progress.total * 100) : 100

  return (
    <section className="rise-1" style={{
      border: '1px solid var(--rule)',
      background: 'var(--paper-2)',
      padding: '22px 26px',
      marginBottom: 18,
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 16 }}>
        <div className="label" style={{ color: 'var(--amber)' }}>Live Feed</div>
        <div className="display" style={{ fontSize: 22, fontVariationSettings: '"opsz" 48' }}>
          Backtesting <em style={{ color: 'var(--amber)' }}>in progress</em>
        </div>
        <div style={{ flex: 1 }} />
        {progress && (
          <div className="numeric" style={{ fontSize: 14, color: 'var(--ink-dim)', letterSpacing: '0.05em' }}>
            {String(progress.current).padStart(2, '0')} / {String(progress.total).padStart(2, '0')}
          </div>
        )}
      </div>

      {/* Progress line */}
      <div style={{ height: 2, background: 'var(--rule)', marginBottom: 14, position: 'relative', overflow: 'hidden' }}>
        <div style={{
          height: '100%', background: 'var(--amber)', width: `${pct}%`,
          boxShadow: '0 0 8px var(--amber-glow)',
          transition: 'width .4s ease',
        }} />
      </div>

      {progress && (
        <div style={{ fontSize: 12, color: 'var(--ink-muted)', marginBottom: liveRows.length ? 16 : 0 }}>
          Scanning <span className="mono" style={{ color: 'var(--ink-dim)' }}>{progress.ticker}</span>
          <span style={{ animation: 'ink-fade 1s infinite' }}>…</span>
        </div>
      )}

      {liveRows.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              {['Ticker','Trades','Win Rate','Total Return'].map(h => (
                <th key={h} className="label" style={{ padding: '6px 0', textAlign: 'left', borderBottom: '1px solid var(--rule)', fontSize: 9 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {liveRows.slice(-5).map(r => {
              const name = r.ticker.replace('.DE','').replace('^','').replace('-USD','').replace('=F','')
              const s    = r.stats
              const rc   = s ? (s.total_return >= 0 ? 'var(--signal-up)' : 'var(--signal-down)') : null
              const wc   = s ? (s.win_rate >= 55 ? 'var(--signal-up)' : s.win_rate >= 45 ? 'var(--amber)' : 'var(--signal-down)') : null
              return (
                <tr key={r.ticker} style={{ borderBottom: '1px solid var(--rule)' }}>
                  <td style={{ padding: '7px 0', fontFamily: 'var(--mono)', color: 'var(--ink)', fontWeight: 500 }}>{name}</td>
                  {s ? (
                    <>
                      <td className="numeric" style={{ padding: '7px 0', color: 'var(--ink-dim)' }}>{s.total_trades}</td>
                      <td className="numeric" style={{ padding: '7px 0', color: wc, fontWeight: 500 }}>{s.win_rate}%</td>
                      <td className="numeric" style={{ padding: '7px 0', color: rc, fontWeight: 500 }}>{s.total_return >= 0 ? '+' : ''}{s.total_return}%</td>
                    </>
                  ) : (
                    <td colSpan={3} style={{ padding: '7px 0', color: 'var(--ink-muted)', fontStyle: 'italic' }}>— no trades generated</td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}

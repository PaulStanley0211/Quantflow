function KPI({ label, value, suffix, sub, color, index }) {
  return (
    <div
      className={`rise-${Math.min(6, index + 1)}`}
      style={{
        borderLeft: `2px solid ${color || 'var(--amber)'}`,
        padding: '14px 18px 16px',
        background: 'var(--paper-2)',
        position: 'relative',
      }}
    >
      <div className="label" style={{ marginBottom: 12 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span className="numeric" style={{
          fontSize: 30, fontWeight: 500, color: color || 'var(--ink)',
          lineHeight: 0.95, letterSpacing: '-0.02em',
        }}>
          {value}
        </span>
        {suffix && (
          <span className="numeric" style={{ fontSize: 14, color: 'var(--ink-muted)', fontWeight: 400 }}>{suffix}</span>
        )}
      </div>
      {sub && (
        <div style={{
          fontSize: 11, color: 'var(--ink-muted)', marginTop: 8, lineHeight: 1.4,
          fontFamily: 'var(--serif)', fontStyle: 'italic',
        }}>{sub}</div>
      )}
    </div>
  )
}

export default function KPICards({ allResults }) {
  const all     = allResults.flatMap(r => r.trades || [])
  const wins    = all.filter(t => t.result === 'WIN')
  const losses  = all.filter(t => t.result === 'LOSS')
  const total   = all.length

  const winRate  = total ? +(wins.length / total * 100).toFixed(1) : 0
  const lossRate = total ? +(losses.length / total * 100).toFixed(1) : 0

  const grossWin  = wins.reduce((s, t) => s + t.pnl_pct, 0)
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl_pct, 0))
  const profitFactor = grossLoss > 0 ? (grossWin / grossLoss).toFixed(2) : '∞'

  const avgHold = total
    ? +(all.reduce((s, t) => s + (t.days_held || 0), 0) / total).toFixed(1)
    : 0

  const avgWin  = wins.length   ? +(grossWin  / wins.length).toFixed(2)  : 0
  const avgLoss = losses.length ? +(grossLoss / losses.length).toFixed(2) : 0

  const withStats = allResults.filter(r => r.stats)
  const best      = withStats.length ? withStats.reduce((a, b) => b.stats.total_return > a.stats.total_return ? b : a) : null

  const totalRet = all.reduce((s, t) => s + t.pnl_pct, 0).toFixed(1)

  const dn = t => t.replace('.DE','').replace('^','').replace('-USD','').replace('=F','')

  const wrColor = winRate  >= 55 ? 'var(--signal-up)' : winRate  >= 45 ? 'var(--amber)' : 'var(--signal-down)'
  const lrColor = lossRate <= 45 ? 'var(--signal-up)' : 'var(--signal-down)'
  const pfColor = profitFactor === '∞' ? 'var(--signal-up)' : parseFloat(profitFactor) >= 1.5 ? 'var(--signal-up)' : parseFloat(profitFactor) >= 1 ? 'var(--amber)' : 'var(--signal-down)'
  const trColor = totalRet >= 0 ? 'var(--signal-up)' : 'var(--signal-down)'

  const cards = [
    { label: 'Total Return',     value: `${totalRet >= 0 ? '+' : ''}${totalRet}`, suffix: '%', color: trColor, sub: `across ${total} trades` },
    { label: 'Win Rate',         value: winRate,         suffix: '%', color: wrColor, sub: `${wins.length} winners` },
    { label: 'Loss Rate',        value: lossRate,        suffix: '%', color: lrColor, sub: `${losses.length} losers` },
    { label: 'Profit Factor',    value: profitFactor,    suffix: '',  color: pfColor, sub: 'gross win ÷ gross loss' },
    { label: 'Avg Win',          value: `+${avgWin}`,    suffix: '%', color: 'var(--signal-up)',   sub: 'per winning trade' },
    { label: 'Avg Loss',         value: `-${avgLoss}`,   suffix: '%', color: 'var(--signal-down)', sub: 'per losing trade' },
    { label: 'Avg Holding',      value: avgHold,         suffix: 'd', color: 'var(--ink)',         sub: 'trading days per trade' },
    { label: 'Lead Performer',   value: best ? dn(best.ticker) : '—', color: 'var(--amber)', sub: best ? `+${best.stats.total_return}% total` : '' },
  ]

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
      gap: 1,
      background: 'var(--rule)',
      border: '1px solid var(--rule)',
      marginBottom: 8,
    }}>
      {cards.map((c, i) => (
        <KPI key={c.label} {...c} index={i} />
      ))}
    </div>
  )
}

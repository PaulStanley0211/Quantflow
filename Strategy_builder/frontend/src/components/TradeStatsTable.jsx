import { useState } from 'react'

function dn(t) { return t.replace('.DE','').replace('^','').replace('-USD','').replace('=F','') }
function getAssetLabel(t) {
  if (t.endsWith('.DE'))  return 'DAX 40'
  if (t.startsWith('^')) return 'German Index'
  if (t.endsWith('-USD')) return 'Crypto'
  if (t.endsWith('=F'))  return 'Commodity'
  return 'Stock'
}

const ASSET_DOT = {
  'DAX 40':       '#f5a623',
  'German Index': '#c084fc',
  'Crypto':       '#4cc9f0',
  'Commodity':    '#3ddc84',
  'Stock':        '#a89f87',
}

const COLS = [
  { key:'name',         label:'Instrument',   align:'left'  },
  { key:'asset',        label:'Class',        align:'left'  },
  { key:'total_trades', label:'N',            align:'right' },
  { key:'wins',         label:'W',            align:'right' },
  { key:'losses',       label:'L',            align:'right' },
  { key:'win_rate',     label:'Win%',         align:'right' },
  { key:'avg_win',      label:'Avg Win',      align:'right' },
  { key:'avg_loss',     label:'Avg Loss',     align:'right' },
  { key:'best_trade',   label:'Best',         align:'right' },
  { key:'worst_trade',  label:'Worst',        align:'right' },
  { key:'total_return', label:'Total Return', align:'right' },
]

export default function TradeStatsTable({ allResults }) {
  const [sortKey, setSortKey] = useState('total_return')
  const [sortAsc, setSortAsc] = useState(false)
  const [filter,  setFilter]  = useState('')

  const rows = allResults
    .filter(r => r.stats && r.stats.total_trades > 0)
    .map(r => ({
      name:         dn(r.ticker),
      ticker:       r.ticker,
      asset:        getAssetLabel(r.ticker),
      total_trades: r.stats.total_trades,
      wins:         r.stats.wins,
      losses:       r.stats.losses,
      win_rate:     r.stats.win_rate,
      avg_win:      r.stats.avg_win,
      avg_loss:     r.stats.avg_loss,
      best_trade:   r.stats.best_trade,
      worst_trade:  r.stats.worst_trade,
      total_return: r.stats.total_return,
    }))
    .filter(r => !filter || r.name.toLowerCase().includes(filter.toLowerCase()) || r.asset.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey]
      if (typeof va === 'string') return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va)
      return sortAsc ? va - vb : vb - va
    })

  const sort = key => {
    if (key === sortKey) setSortAsc(a => !a)
    else { setSortKey(key); setSortAsc(false) }
  }

  const colColor = (key, val) => {
    if (key === 'win_rate')     return val >= 55 ? 'var(--signal-up)' : val >= 45 ? 'var(--amber)' : 'var(--signal-down)'
    if (key === 'total_return') return val >= 0 ? 'var(--signal-up)' : 'var(--signal-down)'
    if (key === 'avg_win' || key === 'best_trade') return 'var(--signal-up)'
    if (key === 'avg_loss' || key === 'worst_trade') return 'var(--signal-down)'
    if (key === 'wins')   return 'var(--signal-up)'
    if (key === 'losses') return 'var(--signal-down)'
    return 'var(--ink-dim)'
  }

  const fmt = (key, val) => {
    if (key === 'win_rate')   return `${val}%`
    if (key === 'total_return') return `${val >= 0 ? '+' : ''}${val}%`
    if (key === 'avg_win' || key === 'best_trade') return `+${val}%`
    if (key === 'avg_loss' || key === 'worst_trade') return `${val}%`
    return val
  }

  return (
    <section style={{
      border: '1px solid var(--rule)',
      background: 'var(--paper-2)',
      padding: '22px 26px', marginBottom: 18,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 18, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div className="label" style={{ color: 'var(--amber)', marginBottom: 6 }}>Table I</div>
          <div className="display" style={{ fontSize: 26, fontVariationSettings:'"opsz" 72' }}>
            Full <em>results ledger</em>
          </div>
          <div style={{ fontSize: 12, color: 'var(--ink-muted)', lineHeight: 1.5, marginTop: 6 }}>
            {rows.length} instruments · click a column to sort
          </div>
        </div>
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter by name or class…"
          style={{
            background: 'var(--paper-3)',
            border: '1px solid var(--rule)',
            padding: '8px 12px',
            color: 'var(--ink)',
            fontFamily: 'var(--sans)', fontSize: 12,
            outline: 'none', width: 220, borderRadius: 0,
          }}
          onFocus={e => { e.target.style.borderColor = 'var(--amber)' }}
          onBlur ={e => { e.target.style.borderColor = 'var(--rule)' }}
        />
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 880 }}>
          <thead>
            <tr>
              {COLS.map(c => (
                <th
                  key={c.key}
                  onClick={() => sort(c.key)}
                  className="label"
                  style={{
                    padding:'10px 14px', textAlign: c.align, fontSize:9,
                    color: sortKey === c.key ? 'var(--amber)' : 'var(--ink-muted)',
                    cursor:'pointer', whiteSpace:'nowrap', userSelect:'none',
                    borderBottom:'1px solid var(--rule-bright)',
                    borderTop:'1px solid var(--rule-bright)',
                  }}
                >
                  {c.label}{sortKey === c.key ? (sortAsc ? ' ↑' : ' ↓') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.ticker}
                style={{
                  borderBottom:'1px solid var(--rule)',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(245,166,35,0.015)',
                  transition: 'background .12s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(245,166,35,0.05)' }}
                onMouseLeave={e => { e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'rgba(245,166,35,0.015)' }}
              >
                <td style={{ padding:'12px 14px', fontFamily:'var(--mono)', fontWeight:500, color:'var(--ink)', whiteSpace:'nowrap' }}>{r.name}</td>
                <td style={{ padding:'12px 14px' }}>
                  <span style={{ display:'inline-flex', alignItems:'center', gap:7, fontSize:10, color:'var(--ink-dim)', textTransform:'uppercase', letterSpacing:'0.1em' }}>
                    <span style={{ width:6, height:6, background: ASSET_DOT[r.asset] }} />
                    {r.asset}
                  </span>
                </td>
                {COLS.slice(2).map(c => (
                  <td
                    key={c.key}
                    className="numeric"
                    style={{
                      padding:'12px 14px', textAlign:c.align,
                      color: colColor(c.key, r[c.key]),
                      fontWeight: c.key === 'total_return' ? 600 : 400,
                    }}
                  >
                    {fmt(c.key, r[c.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && (
        <div style={{ textAlign:'center', color:'var(--ink-muted)', padding:32, fontStyle:'italic', fontFamily:'var(--serif)' }}>
          No results match your filter.
        </div>
      )}
    </section>
  )
}

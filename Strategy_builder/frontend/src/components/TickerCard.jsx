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

function MiniStat({ value, label, color }) {
  return (
    <div style={{ borderLeft: `1px solid var(--rule)`, paddingLeft: 12 }}>
      <div className="numeric" style={{ fontSize:17, fontWeight:500, color, lineHeight:1, marginBottom:6 }}>{value}</div>
      <div className="label" style={{ fontSize:9 }}>{label}</div>
    </div>
  )
}

export default function TickerCard({ result }) {
  const [open, setOpen] = useState(false)
  const { ticker, trades = [], stats: s } = result
  if (!s) return null

  const name       = dn(ticker)
  const assetLabel = getAssetLabel(ticker)
  const rc         = s.total_return >= 0 ? 'var(--signal-up)' : 'var(--signal-down)'
  const wc         = s.win_rate >= 55 ? 'var(--signal-up)' : s.win_rate >= 45 ? 'var(--amber)' : 'var(--signal-down)'
  const lastTrades = trades.slice(-5)

  return (
    <article style={{
      borderTop: '1px solid var(--rule)',
      background: open ? 'var(--paper-2)' : 'transparent',
      transition: 'background .15s',
    }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display:'flex', alignItems:'center', gap:16,
          padding:'18px 4px', cursor:'pointer', userSelect:'none',
        }}
      >
        {/* Asset dot */}
        <div style={{ width:8, height:8, background: ASSET_DOT[assetLabel], flexShrink:0 }} />

        {/* Name + class */}
        <div style={{ minWidth: 140 }}>
          <div style={{ fontFamily:'var(--mono)', fontSize:14, fontWeight:500, color:'var(--ink)', marginBottom:2 }}>{name}</div>
          <div className="label" style={{ fontSize:9 }}>{assetLabel}</div>
        </div>

        <div style={{ flex: 1 }} />

        {/* Stats summary */}
        <div style={{ display:'flex', gap:28, alignItems:'baseline' }}>
          <div style={{ textAlign:'right' }}>
            <div className="numeric" style={{ fontSize:13, color:'var(--ink-dim)', marginBottom:2 }}>{s.total_trades}</div>
            <div className="label" style={{ fontSize:9 }}>Trades</div>
          </div>
          <div style={{ textAlign:'right' }}>
            <div className="numeric" style={{ fontSize:13, color: wc, fontWeight:500, marginBottom:2 }}>{s.win_rate}%</div>
            <div className="label" style={{ fontSize:9 }}>Win Rate</div>
          </div>
          <div style={{ textAlign:'right', minWidth:90 }}>
            <div className="numeric" style={{ fontSize:20, color: rc, fontWeight:500, lineHeight:1, marginBottom:4 }}>
              {s.total_return >= 0 ? '+' : ''}{s.total_return}%
            </div>
            <div className="label" style={{ fontSize:9 }}>Total Return</div>
          </div>
          <div style={{
            fontSize:11, color:'var(--ink-muted)',
            transform: open ? 'rotate(90deg)' : 'none',
            transition: 'transform .2s',
            fontFamily:'var(--mono)',
          }}>▸</div>
        </div>
      </div>

      {open && (
        <div style={{ padding: '0 4px 22px', animation:'ink-fade .25s ease' }}>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:0, marginBottom:18, paddingTop:6, paddingBottom:12, borderTop:'1px solid var(--rule)' }}>
            <MiniStat value={`+${s.avg_win}%`}     label="Avg Win"     color="var(--signal-up)" />
            <MiniStat value={`${s.avg_loss}%`}     label="Avg Loss"    color="var(--signal-down)" />
            <MiniStat value={`+${s.best_trade}%`}  label="Best Trade"  color="var(--signal-up)" />
            <MiniStat value={`${s.worst_trade}%`}  label="Worst Trade" color="var(--signal-down)" />
          </div>

          {lastTrades.length > 0 && (
            <>
              <div className="label" style={{ marginBottom:8 }}>Last {lastTrades.length} Trades</div>
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
                <thead>
                  <tr>
                    {['Entry','Exit','Buy','Sell','P&L','Reason'].map(h => (
                      <th key={h} className="label" style={{ padding:'6px 10px', textAlign:'left', fontSize:9, borderBottom:'1px solid var(--rule)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {lastTrades.map((t, i) => {
                    const pc = t.pnl_pct >= 0 ? 'var(--signal-up)' : 'var(--signal-down)'
                    const ps = t.pnl_pct >= 0 ? '+' : ''
                    return (
                      <tr key={i} style={{ borderBottom:'1px solid var(--rule)' }}>
                        <td style={{ padding:'8px 10px', fontFamily:'var(--mono)', color:'var(--ink-muted)', fontSize:11 }}>{t.entry_date}</td>
                        <td style={{ padding:'8px 10px', fontFamily:'var(--mono)', color:'var(--ink-muted)', fontSize:11 }}>{t.exit_date}</td>
                        <td className="numeric" style={{ padding:'8px 10px', color:'var(--ink-dim)' }}>{t.entry_price}</td>
                        <td className="numeric" style={{ padding:'8px 10px', color:'var(--ink-dim)' }}>{t.exit_price}</td>
                        <td className="numeric" style={{ padding:'8px 10px', color:pc, fontWeight:500 }}>{ps}{t.pnl_pct}%</td>
                        <td style={{ padding:'8px 10px', color:'var(--ink-muted)', fontSize:11, fontStyle:'italic' }}>{t.exit_reason}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </article>
  )
}

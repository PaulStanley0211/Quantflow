import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
  ReferenceLine, ResponsiveContainer, CartesianGrid, LabelList,
} from 'recharts'

function dn(t) { return t.replace('.DE','').replace('^','').replace('-USD','').replace('=F','') }

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{
      background: 'var(--paper-2)', border: '1px solid var(--rule-bright)',
      padding: '10px 14px', fontSize: 12, minWidth: 190,
      boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
    }}>
      <div style={{ fontFamily:'var(--serif)', fontStyle:'italic', fontSize:15, color:'var(--ink)', marginBottom:6 }}>{label}</div>
      <div className="numeric" style={{ fontSize:18, color: d.win_rate >= 55 ? 'var(--signal-up)' : d.win_rate >= 45 ? 'var(--amber)' : 'var(--signal-down)', fontWeight:500, marginBottom:8 }}>
        {d.win_rate}%
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'auto 1fr', gap:'3px 14px', fontSize:11 }}>
        <span style={{ color:'var(--ink-muted)' }}>Wins</span><span className="numeric" style={{ color:'var(--signal-up)' }}>{d.wins}</span>
        <span style={{ color:'var(--ink-muted)' }}>Losses</span><span className="numeric" style={{ color:'var(--signal-down)' }}>{d.losses}</span>
        <span style={{ color:'var(--ink-muted)' }}>Total</span><span className="numeric" style={{ color:'var(--ink-dim)' }}>{d.total_trades}</span>
      </div>
    </div>
  )
}

export default function WinRateChart({ allResults }) {
  const data = allResults
    .filter(r => r.stats && r.stats.total_trades > 0)
    .map(r => ({
      name:         dn(r.ticker),
      win_rate:     r.stats.win_rate,
      wins:         r.stats.wins,
      losses:       r.stats.losses,
      total_trades: r.stats.total_trades,
    }))
    .sort((a, b) => b.win_rate - a.win_rate)

  const chartH = Math.max(460, data.length * 26)

  return (
    <section style={{
      border: '1px solid var(--rule)',
      background: 'var(--paper-2)',
      padding: '22px 26px',
    }}>
      <div style={{ marginBottom: 18 }}>
        <div className="label" style={{ color: 'var(--amber)', marginBottom: 6 }}>Figure II</div>
        <div className="display" style={{ fontSize: 26, fontVariationSettings:'"opsz" 72', marginBottom: 8 }}>
          Win Rate<br /><em>by Instrument</em>
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-muted)', lineHeight: 1.5 }}>
          Percentage of profitable trades. The dashed line marks coin-flip territory.
        </div>
      </div>

      <div style={{ display:'flex', gap:18, marginBottom:14, paddingBottom:12, borderBottom:'1px solid var(--rule)' }}>
        {[
          { l: '≥ 55% · strong',  c: 'var(--signal-up)'   },
          { l: '45–55% · neutral', c: 'var(--amber)'       },
          { l: '< 45% · weak',     c: 'var(--signal-down)' },
        ].map(x => (
          <span key={x.l} style={{ fontSize:10, color:'var(--ink-dim)', display:'flex', alignItems:'center', gap:6, textTransform:'uppercase', letterSpacing:'0.12em' }}>
            <span style={{ width:10, height:10, background: x.c }} />{x.l}
          </span>
        ))}
      </div>

      <div style={{ overflowY:'auto', maxHeight:500 }}>
        <ResponsiveContainer width="100%" height={chartH}>
          <BarChart layout="vertical" data={data} margin={{ left:6, right:60, top:4, bottom:4 }}>
            <CartesianGrid strokeDasharray="2 3" stroke="#1c1813" horizontal={false} />
            <XAxis
              type="number" domain={[0, 100]}
              tick={{ fill:'#6e664f', fontSize:10, fontFamily:'JetBrains Mono' }}
              tickFormatter={v => `${v}%`}
              axisLine={{ stroke:'#2e2820' }} tickLine={false}
            />
            <YAxis
              type="category" dataKey="name" width={56}
              tick={{ fill:'#a89f87', fontSize:10, fontFamily:'JetBrains Mono' }}
              axisLine={false} tickLine={false}
            />
            <ReferenceLine x={50} stroke="#44392a" strokeDasharray="4 4" strokeWidth={1} />
            <Tooltip content={<Tip />} cursor={{ fill:'rgba(245,166,35,0.06)' }} />
            <Bar dataKey="win_rate" radius={0} maxBarSize={18}>
              {data.map((d, i) => (
                <Cell key={i}
                  fill={d.win_rate >= 55 ? '#3ddc84' : d.win_rate >= 45 ? '#f5a623' : '#ff5757'}
                  opacity={0.9}
                />
              ))}
              <LabelList
                dataKey="win_rate" position="right"
                style={{ fill:'#a89f87', fontSize:10, fontFamily:'JetBrains Mono' }}
                formatter={v => `${v}%`}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

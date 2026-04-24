import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
  ReferenceLine, ResponsiveContainer, CartesianGrid, LabelList,
} from 'recharts'

const ASSET_COLORS = {
  'DAX 40':       '#f5a623',  // signature amber
  'German Index': '#c084fc',  // plum
  'Crypto':       '#4cc9f0',  // sky
  'Commodity':    '#3ddc84',  // mint
}

function getAssetLabel(ticker) {
  if (ticker.endsWith('.DE'))  return 'DAX 40'
  if (ticker.startsWith('^')) return 'German Index'
  if (ticker.endsWith('-USD')) return 'Crypto'
  if (ticker.endsWith('=F'))  return 'Commodity'
  return 'Stock'
}

function dn(t) { return t.replace('.DE','').replace('^','').replace('-USD','').replace('=F','') }

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const val = payload[0].value
  return (
    <div style={{
      background: 'var(--paper-2)', border: '1px solid var(--rule-bright)',
      padding: '10px 14px', fontSize: 12, minWidth: 180,
      boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
    }}>
      <div style={{ fontFamily:'var(--serif)', fontStyle:'italic', fontSize:15, color:'var(--ink)', marginBottom:6 }}>{label}</div>
      <div className="label" style={{ fontSize:9, marginBottom:8 }}>{d.asset}</div>
      <div className="numeric" style={{ fontSize:18, color: val >= 0 ? 'var(--signal-up)' : 'var(--signal-down)', fontWeight:500 }}>
        {val >= 0 ? '+' : ''}{val}%
      </div>
      <div style={{ fontSize:10, color:'var(--ink-muted)', marginTop:4, fontFamily:'var(--mono)' }}>
        {d.total_trades} trades · {d.win_rate}% WR
      </div>
    </div>
  )
}

export default function ReturnsBarChart({ allResults }) {
  const data = allResults
    .filter(r => r.stats)
    .map(r => ({
      name:          dn(r.ticker),
      ticker:        r.ticker,
      asset:         getAssetLabel(r.ticker),
      total_return:  r.stats.total_return,
      win_rate:      r.stats.win_rate,
      total_trades:  r.stats.total_trades,
    }))
    .sort((a, b) => b.total_return - a.total_return)

  const chartH = Math.max(460, data.length * 26)

  return (
    <section style={{
      border: '1px solid var(--rule)',
      background: 'var(--paper-2)',
      padding: '22px 26px',
    }}>
      <div style={{ marginBottom: 18 }}>
        <div className="label" style={{ color: 'var(--amber)', marginBottom: 6 }}>Figure I</div>
        <div className="display" style={{ fontSize: 26, fontVariationSettings:'"opsz" 72', marginBottom: 8 }}>
          Total Return<br /><em>by Instrument</em>
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-muted)', lineHeight: 1.5 }}>
          Cumulative P&L percentage across every backtested trade, sorted by magnitude.
        </div>
      </div>

      {/* Legend */}
      <div style={{ display:'flex', gap:16, flexWrap:'wrap', marginBottom:14, paddingBottom:12, borderBottom:'1px solid var(--rule)' }}>
        {Object.entries(ASSET_COLORS).map(([label, color]) => (
          <span key={label} style={{ fontSize:10, color:'var(--ink-dim)', display:'flex', alignItems:'center', gap:6, textTransform:'uppercase', letterSpacing:'0.12em' }}>
            <span style={{ width:10, height:10, background: color }} />
            {label}
          </span>
        ))}
      </div>

      <div style={{ overflowY:'auto', maxHeight:500 }}>
        <ResponsiveContainer width="100%" height={chartH}>
          <BarChart layout="vertical" data={data} margin={{ left: 6, right: 60, top: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="2 3" stroke="#1c1813" horizontal={false} />
            <XAxis
              type="number" domain={['auto','auto']}
              tick={{ fill:'#6e664f', fontSize:10, fontFamily:'JetBrains Mono' }}
              tickFormatter={v => `${v > 0 ? '+' : ''}${v}%`}
              axisLine={{ stroke:'#2e2820' }}
              tickLine={false}
            />
            <YAxis
              type="category" dataKey="name" width={56}
              tick={{ fill:'#a89f87', fontSize:10, fontFamily:'JetBrains Mono' }}
              axisLine={false} tickLine={false}
            />
            <ReferenceLine x={0} stroke="#44392a" strokeWidth={1} />
            <Tooltip content={<Tip />} cursor={{ fill:'rgba(245,166,35,0.06)' }} />
            <Bar dataKey="total_return" radius={0} maxBarSize={18}>
              {data.map((d, i) => (
                <Cell key={i}
                  fill={d.total_return >= 0 ? ASSET_COLORS[d.asset] || '#3ddc84' : '#ff5757'}
                  opacity={d.total_return >= 0 ? 1 : 0.85}
                />
              ))}
              <LabelList
                dataKey="total_return" position="right"
                style={{ fill:'#a89f87', fontSize:10, fontFamily:'JetBrains Mono' }}
                formatter={v => `${v >= 0 ? '+' : ''}${v}%`}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

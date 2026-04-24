import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'

function dn(t) { return t.replace('.DE','').replace('^','').replace('-USD','').replace('=F','') }

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--paper-2)', border: '1px solid var(--rule-bright)',
      padding: '10px 14px', fontSize: 12,
      boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
    }}>
      <div style={{ fontFamily:'var(--serif)', fontStyle:'italic', fontSize:15, color:'var(--ink)', marginBottom:6 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} className="numeric" style={{ color: p.name === 'wins' ? 'var(--signal-up)' : 'var(--signal-down)', fontSize:13 }}>
          {p.name === 'wins' ? 'Wins' : 'Losses'} · <b>{p.value}</b>
        </div>
      ))}
    </div>
  )
}

export default function WinsLossesChart({ allResults }) {
  const data = allResults
    .filter(r => r.stats && r.stats.total_trades > 0)
    .map(r => ({ name: dn(r.ticker), wins: r.stats.wins, losses: r.stats.losses }))
    .sort((a, b) => (b.wins + b.losses) - (a.wins + a.losses))

  const chartH = Math.max(400, data.length * 22)

  return (
    <section style={{
      border: '1px solid var(--rule)',
      background: 'var(--paper-2)',
      padding: '22px 26px',
    }}>
      <div style={{ marginBottom: 18 }}>
        <div className="label" style={{ color: 'var(--amber)', marginBottom: 6 }}>Figure III</div>
        <div className="display" style={{ fontSize: 26, fontVariationSettings:'"opsz" 72', marginBottom: 8 }}>
          Wins <em style={{ color: 'var(--ink-dim)' }}>vs</em> Losses
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-muted)', lineHeight: 1.5 }}>
          Absolute count of profitable versus unprofitable trades, grouped side-by-side.
        </div>
      </div>

      <div style={{ overflowY:'auto', maxHeight:440 }}>
        <ResponsiveContainer width="100%" height={chartH}>
          <BarChart layout="vertical" data={data} margin={{ left:6, right:20, top:4, bottom:4 }} barGap={2}>
            <CartesianGrid strokeDasharray="2 3" stroke="#1c1813" horizontal={false} />
            <XAxis type="number" tick={{ fill:'#6e664f', fontSize:10, fontFamily:'JetBrains Mono' }} axisLine={{ stroke:'#2e2820' }} tickLine={false} />
            <YAxis type="category" dataKey="name" width={56} tick={{ fill:'#a89f87', fontSize:10, fontFamily:'JetBrains Mono' }} axisLine={false} tickLine={false} />
            <Tooltip content={<Tip />} cursor={{ fill:'rgba(245,166,35,0.06)' }} />
            <Legend
              wrapperStyle={{ fontSize:10, color:'var(--ink-muted)', paddingTop:8, textTransform:'uppercase', letterSpacing:'0.14em' }}
              iconType="square"
              formatter={v => v === 'wins' ? 'Wins' : 'Losses'}
            />
            <Bar dataKey="wins"   fill="#3ddc84" opacity={0.9}  radius={0} maxBarSize={9} />
            <Bar dataKey="losses" fill="#ff5757" opacity={0.85} radius={0} maxBarSize={9} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

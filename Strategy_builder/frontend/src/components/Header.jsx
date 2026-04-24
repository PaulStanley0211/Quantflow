import { useEffect, useState } from 'react'

export default function Header({ running, status }) {
  const [clock, setClock] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const hh = String(clock.getHours()).padStart(2,'0')
  const mm = String(clock.getMinutes()).padStart(2,'0')
  const ss = String(clock.getSeconds()).padStart(2,'0')

  const statusText = running ? 'RUNNING' : status === 'error' ? 'ERROR' : status === 'done' ? 'COMPLETE' : 'STANDBY'
  const statusColor = running ? 'var(--amber)' : status === 'error' ? 'var(--signal-down)' : status === 'done' ? 'var(--signal-up)' : 'var(--ink-muted)'

  return (
    <header style={{
      height: 'var(--header-h)',
      display: 'flex', alignItems: 'center',
      padding: '0 28px', gap: 24,
      borderBottom: '1px solid var(--rule)',
      background: 'var(--paper)',
      position: 'relative', zIndex: 10,
    }}>
      {/* Q mark — amber square */}
      <div style={{
        width: 40, height: 40,
        background: 'var(--amber)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--serif)', fontStyle: 'italic', fontWeight: 600,
        fontSize: 26, color: 'var(--paper)',
        letterSpacing: '-0.02em',
      }}>Q</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <div style={{
          fontFamily: 'var(--serif)', fontStyle: 'italic', fontWeight: 500,
          fontVariationSettings: '"opsz" 48',
          fontSize: 22, lineHeight: 1, color: 'var(--ink)',
          letterSpacing: '-0.015em',
        }}>QuantFlow</div>
        <div style={{
          fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.24em',
          color: 'var(--ink-muted)', fontWeight: 500,
        }}>The Strategy Builder</div>
      </div>

      <div style={{ width: 1, height: 30, background: 'var(--rule)' }} />

      {/* Masthead-style dateline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div className="label">Watchlist</div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-dim)', letterSpacing: '0.02em' }}>
          DAX·40 &nbsp;/&nbsp; IDX·4 &nbsp;/&nbsp; CRYPTO·5 &nbsp;/&nbsp; COMM·5
        </div>
      </div>

      {/* Right side */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{
          fontFamily: 'var(--mono)', fontSize: 13,
          color: 'var(--ink-dim)', letterSpacing: '0.06em',
        }}>
          {hh}<span style={{ opacity: .4 }}>:</span>{mm}<span style={{ opacity: .4 }}>:</span>{ss}
        </div>

        <div style={{ width: 1, height: 20, background: 'var(--rule)' }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: statusColor,
            boxShadow: `0 0 10px ${statusColor}`,
            animation: running ? 'amber-pulse 1.4s infinite' : 'none',
          }} />
          <span style={{
            fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
            color: statusColor, letterSpacing: '0.14em',
          }}>{statusText}</span>
        </div>
      </div>
    </header>
  )
}

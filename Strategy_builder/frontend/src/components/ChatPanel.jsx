import { useRef, useEffect, useState } from 'react'

const TEMPLATES = [
  { name: 'RSI Bounce',      text: 'Buy when RSI drops below 30 and price is above the 200 EMA. Sell when RSI rises above 70 or price drops 3% from entry.' },
  { name: 'EMA Crossover',   text: 'Buy when the 21 EMA crosses above the 50 EMA with volume above average. Sell when 21 EMA crosses back below 50 EMA.' },
  { name: 'Breakout',        text: 'Buy when price breaks above the 20-day high with volume at least 1.5x the 20-day average. Sell when price drops 2% below the breakout level.' },
  { name: 'Pullback 21 EMA', text: 'Buy when price pulls back to within 1% of the 21 EMA in an uptrend (price above 50 EMA). Sell when price hits 3x the initial risk or drops below the 50 EMA.' },
  { name: 'Momentum Surge',  text: 'Buy when price rises more than 2% in one day with volume above 2x average and RSI between 55 and 75. Sell after 5 days or when RSI drops below 50.' },
]

function TypingDots() {
  return (
    <div style={{ display: 'flex', gap: 5, padding: '4px 0' }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 6, height: 6, borderRadius: '50%', background: 'var(--amber)',
          animation: `typing-bounce 1.2s infinite ${i * 0.18}s`,
        }} />
      ))}
    </div>
  )
}

export default function ChatPanel({ messages, running, onRun }) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef    = useRef(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const submit = () => {
    const text = input.trim()
    if (!text || running) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    onRun(text)
  }

  const onKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  const onInput = e => {
    setInput(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px'
  }

  return (
    <aside style={{
      width: 'var(--sidebar-w)', flexShrink: 0,
      borderRight: '1px solid var(--rule)',
      display: 'flex', flexDirection: 'column',
      background: 'var(--paper-2)',
      overflow: 'hidden', position: 'relative', zIndex: 2,
    }}>
      {/* Editorial masthead */}
      <div style={{ padding: '22px 24px 18px', borderBottom: '1px solid var(--rule)' }}>
        <div className="label" style={{ color: 'var(--amber)', marginBottom: 6 }}>Briefing</div>
        <div className="display" style={{
          fontSize: 26, lineHeight: 1.05, fontVariationSettings: '"opsz" 72', marginBottom: 4,
        }}>
          Describe your<br />strategy, <em style={{ color: 'var(--amber)' }}>in prose.</em>
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-muted)', lineHeight: 1.6, marginTop: 10 }}>
          The parser will convert your English into executable rules and backtest across 54 instruments.
        </div>
      </div>

      {/* Templates */}
      <div style={{ padding: '16px 24px 4px' }}>
        <div className="label" style={{ marginBottom: 10 }}>Quick Templates</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {TEMPLATES.map((t, i) => (
            <button
              key={t.name}
              onClick={() => { setInput(t.text); textareaRef.current?.focus() }}
              style={{
                background: 'transparent', border: '1px solid var(--rule)',
                color: 'var(--ink-dim)', padding: '5px 12px',
                fontFamily: 'var(--sans)', fontSize: 11, fontWeight: 500,
                letterSpacing: '0.03em', cursor: 'pointer',
                transition: 'all .15s ease',
                borderRadius: 0,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--amber)'
                e.currentTarget.style.color       = 'var(--amber)'
                e.currentTarget.style.background  = 'var(--amber-soft)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--rule)'
                e.currentTarget.style.color       = 'var(--ink-dim)'
                e.currentTarget.style.background  = 'transparent'
              }}
            >{t.name}</button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {messages.map((msg, i) => {
          if (msg.type === 'typing') return (
            <div key={i} style={{ display: 'flex', gap: 10, animation: 'ink-fade .25s ease' }}>
              <Avatar type="ai" />
              <Bubble type="ai"><TypingDots /></Bubble>
            </div>
          )

          if (msg.type === 'system') return (
            <div key={i} style={{ textAlign: 'center', fontSize: 10, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.15em' }}>{msg.text}</div>
          )

          const isUser = msg.type === 'user'
          return (
            <div key={i} style={{ display: 'flex', gap: 10, flexDirection: isUser ? 'row-reverse' : 'row', animation: 'ink-fade .3s ease' }}>
              <Avatar type={msg.type} />
              <Bubble type={msg.type} html={msg.text} />
            </div>
          )
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ borderTop: '1px solid var(--rule)', padding: '16px 24px 20px', background: 'var(--paper-2)' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={onInput}
            onKeyDown={onKeyDown}
            disabled={running}
            placeholder="e.g. Buy when RSI drops below 30…"
            rows={2}
            style={{
              flex: 1,
              background: 'var(--paper-3)',
              border: '1px solid var(--rule)',
              borderRadius: 4,
              padding: '12px 14px',
              color: 'var(--ink)',
              fontSize: 14,
              fontFamily: 'var(--sans)',
              resize: 'none',
              minHeight: 48, maxHeight: 140,
              lineHeight: 1.5,
              outline: 'none',
              opacity: running ? 0.5 : 1,
              transition: 'border-color .15s',
            }}
            onFocus={e => { e.target.style.borderColor = 'var(--amber)' }}
            onBlur ={e => { e.target.style.borderColor = 'var(--rule)' }}
          />
          <button
            onClick={submit}
            disabled={running || !input.trim()}
            style={{
              width: 48, height: 48,
              background: (running || !input.trim()) ? 'var(--paper-3)' : 'var(--amber)',
              border: 'none', borderRadius: 4,
              cursor: (running || !input.trim()) ? 'not-allowed' : 'pointer',
              color: (running || !input.trim()) ? 'var(--ink-muted)' : 'var(--paper)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, transition: 'all .15s',
            }}
            onMouseEnter={e => { if (!running && input.trim()) e.currentTarget.style.background = 'var(--amber-hot)' }}
            onMouseLeave={e => { if (!running && input.trim()) e.currentTarget.style.background = 'var(--amber)' }}
          >
            <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <div style={{ fontSize: 9, color: 'var(--ink-muted)', marginTop: 10, textAlign: 'center', textTransform: 'uppercase', letterSpacing: '0.2em' }}>
          Enter to send &nbsp;·&nbsp; Shift+Enter for new line
        </div>
      </div>
    </aside>
  )
}

function Avatar({ type }) {
  const isUser = type === 'user'
  return (
    <div style={{
      width: 30, height: 30, flexShrink: 0, marginTop: 2,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--serif)', fontStyle: 'italic', fontWeight: 600,
      fontSize: 15,
      background: isUser ? 'var(--ink)' : 'var(--amber)',
      color: 'var(--paper)',
    }}>{isUser ? 'P' : 'Q'}</div>
  )
}

function Bubble({ type, html, children }) {
  const isUser = type === 'user'
  const content = children ?? (
    <span dangerouslySetInnerHTML={{ __html: html }} />
  )
  return (
    <div style={{
      maxWidth: 300,
      padding: '11px 14px',
      fontSize: 13.5, lineHeight: 1.6,
      background: isUser ? 'var(--paper-4)' : 'var(--paper-3)',
      border: '1px solid var(--rule)',
      borderLeft: isUser ? '1px solid var(--rule)' : '2px solid var(--amber)',
      borderRadius: 2,
      color: 'var(--ink)',
    }}>
      {content}
    </div>
  )
}

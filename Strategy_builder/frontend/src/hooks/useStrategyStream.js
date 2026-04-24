import { useState, useRef, useCallback } from 'react'

export function useStrategyStream() {
  const [state, setState] = useState({
    running: false,
    rules: null,
    progress: null,        // { current, total, ticker }
    liveRows: [],          // per-ticker results as they come in
    stats: null,
    chart: null,
    allResults: [],
    messages: [
      { type: 'ai', text: 'Hi! Describe your trading strategy in plain English and I\'ll backtest it across the full watchlist. Or pick a template above to get started.' }
    ],
    error: null,
  })

  const abortRef = useRef(null)

  const addMsg = useCallback((text, type = 'ai') => {
    setState(s => ({ ...s, messages: [...s.messages, { type, text }] }))
  }, [])

  const run = useCallback(async (strategyText) => {
    setState(s => ({
      ...s,
      running: true,
      rules: null,
      progress: null,
      liveRows: [],
      stats: null,
      chart: null,
      allResults: [],
      error: null,
      messages: [...s.messages, { type: 'user', text: strategyText }, { type: 'typing' }],
    }))

    try {
      const res = await fetch('/api/strategy/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy: strategyText }),
      })

      if (!res.ok) throw new Error(`Server error ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let evt
          try { evt = JSON.parse(line.slice(6)) } catch { continue }

          switch (evt.type) {
            case 'status':
              setState(s => ({
                ...s,
                messages: s.messages.filter(m => m.type !== 'typing').concat({ type: 'ai', text: evt.message }, { type: 'typing' }),
              }))
              break

            case 'rules':
              setState(s => ({
                ...s,
                rules: evt.rules,
                messages: s.messages.filter(m => m.type !== 'typing').concat({
                  type: 'ai',
                  text: `Strategy parsed: <b>${evt.rules.strategy_name}</b> — ${evt.rules.entry_conditions?.length || 0} entry condition(s), ${evt.rules.exit_conditions?.length || 0} exit condition(s).`,
                }),
              }))
              break

            case 'progress':
              setState(s => ({ ...s, progress: { current: evt.current, total: evt.total, ticker: evt.ticker } }))
              break

            case 'ticker_done':
              setState(s => ({
                ...s,
                liveRows: [...s.liveRows, { ticker: evt.ticker, stats: evt.stats, tradeCount: evt.trade_count }],
              }))
              break

            case 'complete': {
              const all = evt.all_results.flatMap(r => r.trades || [])
              const wins = all.filter(t => t.result === 'WIN')
              const wr = all.length ? (wins.length / all.length * 100).toFixed(1) : 0
              const losses = all.filter(t => t.result === 'LOSS')
              const avgRet = all.length ? (all.reduce((s, t) => s + t.pnl_pct, 0) / all.length).toFixed(2) : 0
              const best = evt.all_results.filter(r => r.stats).sort((a, b) => b.stats.total_return - a.stats.total_return)[0]

              setState(s => ({
                ...s,
                running: false,
                progress: null,
                chart: evt.chart,
                allResults: evt.all_results,
                stats: { total: all.length, winRate: wr, avgReturn: avgRet, wins: wins.length, losses: losses.length },
                messages: s.messages.filter(m => m.type !== 'typing').concat({
                  type: 'ai',
                  text: `Backtest complete — <b>${all.length} trades</b> across ${evt.all_results.length} instruments · <b>${wr}% win rate</b>${best ? ` · Best: <b>${best.ticker.replace('.DE', '').replace('^', '').replace('-USD', '').replace('=F', '')} (+${best.stats.total_return}%)</b>` : ''}.`,
                }),
              }))
              break
            }

            case 'error':
              setState(s => ({
                ...s,
                running: false,
                error: evt.message,
                messages: s.messages.filter(m => m.type !== 'typing').concat({ type: 'ai', text: `Error: ${evt.message}` }),
              }))
              break
          }
        }
      }
    } catch (err) {
      setState(s => ({
        ...s,
        running: false,
        error: err.message,
        messages: s.messages.filter(m => m.type !== 'typing').concat({ type: 'ai', text: `Something went wrong: ${err.message}` }),
      }))
    }
  }, [])

  return { state, run }
}

import { useStrategyStream }    from './hooks/useStrategyStream'
import Header                  from './components/Header'
import ChatPanel               from './components/ChatPanel'
import StrategyCard            from './components/StrategyCard'
import KPICards                from './components/KPICards'
import ProgressSection         from './components/ProgressSection'
import ReturnsBarChart         from './components/charts/ReturnsBarChart'
import WinRateChart            from './components/charts/WinRateChart'
import WinsLossesChart         from './components/charts/WinsLossesChart'
import TradeStatsTable         from './components/TradeStatsTable'
import TickerCard              from './components/TickerCard'
import EmptyState              from './components/EmptyState'
import SectionHeader           from './components/SectionHeader'

export default function App() {
  const { state, run } = useStrategyStream()
  const { running, rules, progress, liveRows, allResults, messages, error } = state

  const hasResults   = allResults.length > 0
  const statusFlag   = error ? 'error' : hasResults ? 'done' : 'idle'
  const showProgress = running || (liveRows.length > 0 && !hasResults)

  const sorted = allResults
    .filter(r => r.stats)
    .sort((a, b) => b.stats.total_return - a.stats.total_return)

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', position:'relative' }}>
      <Header running={running} status={statusFlag} />

      <div style={{ display:'flex', flex:1, overflow:'hidden', position:'relative', zIndex:2 }}>
        <ChatPanel messages={messages} running={running} onRun={run} />

        <main style={{
          flex: 1, overflowY: 'auto',
          padding: '28px 48px 80px',
          background: 'var(--paper)',
          position: 'relative',
        }}>
          {!rules && !running && !hasResults ? (
            <EmptyState />
          ) : (
            <div style={{ maxWidth: 1280, margin: '0 auto' }}>
              <StrategyCard rules={rules} />

              {showProgress && <ProgressSection progress={progress} liveRows={liveRows} />}

              {hasResults && (
                <>
                  <SectionHeader eyebrow="Section I · Performance" title="At a Glance" />
                  <KPICards allResults={allResults} />

                  <SectionHeader eyebrow="Section II · Return Analysis" title="Returns by Ticker" />
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:1, background:'var(--rule)', border:'1px solid var(--rule)' }}>
                    <ReturnsBarChart allResults={allResults} />
                    <WinRateChart    allResults={allResults} />
                  </div>

                  <SectionHeader eyebrow="Section III · Distribution" title="Winners & Losers" />
                  <WinsLossesChart allResults={allResults} />

                  <SectionHeader eyebrow="Section IV · Ledger" title="The Full Record" count={sorted.length} />
                  <TradeStatsTable allResults={allResults} />

                  <SectionHeader eyebrow="Section V · Trade Detail" title="By Instrument" count={sorted.length} />
                  <div style={{ border:'1px solid var(--rule)', background:'var(--paper-2)', padding: '0 22px' }}>
                    {sorted.map(r => <TickerCard key={r.ticker} result={r} />)}
                  </div>

                  {sorted.length === 0 && (
                    <div style={{ textAlign:'center', color:'var(--ink-muted)', padding:40, fontStyle:'italic', fontFamily:'var(--serif)', fontSize:16 }}>
                      No trades were generated for any ticker with this strategy.
                    </div>
                  )}

                  {/* Colophon */}
                  <footer style={{ marginTop:60, paddingTop:20, borderTop:'1px solid var(--rule)', display:'flex', justifyContent:'space-between', alignItems:'baseline', flexWrap:'wrap', gap:14 }}>
                    <div style={{ fontFamily:'var(--serif)', fontStyle:'italic', fontSize:14, color:'var(--ink-muted)' }}>
                      — Past performance does not guarantee future results.
                    </div>
                    <div className="label" style={{ color: 'var(--ink-faint)' }}>
                      QuantFlow · {new Date().getFullYear()}
                    </div>
                  </footer>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

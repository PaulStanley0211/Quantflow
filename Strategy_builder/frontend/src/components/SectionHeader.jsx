export default function SectionHeader({ eyebrow, title, rule = true, count }) {
  return (
    <div style={{ marginTop: 36, marginBottom: 18 }}>
      {eyebrow && (
        <div className="label" style={{ marginBottom: 10, color: 'var(--amber)' }}>
          {eyebrow}
          {count !== undefined && (
            <span style={{ marginLeft: 10, color: 'var(--ink-muted)', fontFamily: 'var(--mono)', letterSpacing: 'normal', textTransform: 'none' }}>
              / {count}
            </span>
          )}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
        <h2 className="display" style={{
          fontSize: 'clamp(32px, 4.4vw, 52px)',
          fontVariationSettings: '"opsz" 144',
          fontWeight: 500,
        }}>{title}</h2>
        {rule && <div style={{ flex: 1, height: 1, background: 'var(--rule)', marginBottom: 10 }} />}
      </div>
    </div>
  )
}

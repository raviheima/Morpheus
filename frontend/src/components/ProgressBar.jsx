export default function ProgressBar({ value, label, sub }) {
  const pct = value == null ? null : Math.max(0, Math.min(100, value));
  return (
    <div className="progress-wrap">
      {label ? <strong>{label}</strong> : null}
      <div className={`progress ${pct == null ? "indeterminate" : ""}`}>
        <i style={pct != null ? { width: `${pct}%` } : undefined} />
      </div>
      {sub ? <small style={{ color: "var(--muted)", fontSize: 13 }}>{sub}</small> : null}
    </div>
  );
}

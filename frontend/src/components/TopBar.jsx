export default function TopBar({ user, caseLabel, onLogout, onCases }) {
  const initials = (user || "")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "U";

  return (
    <header className="topbar">
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="brand-icon" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </span>
        <span className="topbar-brand">MORPHEUS</span>
      </div>
      {caseLabel ? (
        <span className="topbar-case">
          Case <strong>{caseLabel}</strong>
        </span>
      ) : null}
      <div className="topbar-actions">
        {onCases ? (
          <button type="button" className="btn btn-sm btn-cases" onClick={onCases}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            Cases
          </button>
        ) : null}
        <span className="topbar-avatar" title={user}>{initials}</span>
        <span className="topbar-user">{user}</span>
        <button type="button" className="btn btn-ghost" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </header>
  );
}

export default function TopBar({ user, caseLabel, onLogout, onCases }) {
  return (
    <header className="topbar">
      <span className="topbar-brand">MORPHEUS</span>
      {caseLabel ? (
        <span className="topbar-case">
          Case <strong>{caseLabel}</strong>
        </span>
      ) : null}
      <div className="topbar-actions">
        {onCases ? (
          <button type="button" className="btn btn-ghost" onClick={onCases}>
            Cases
          </button>
        ) : null}
        <span className="topbar-user">{user}</span>
        <button type="button" className="btn btn-ghost" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </header>
  );
}

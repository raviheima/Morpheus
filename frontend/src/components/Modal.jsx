export default function Modal({ title, children, onClose, wide }) {
  return (
    <div className="modal-back" onClick={onClose} role="presentation">
      <div
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <span>{title}</span>
          <button type="button" className="btn btn-sm" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="body">{children}</div>
      </div>
    </div>
  );
}

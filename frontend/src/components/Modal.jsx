export default function Modal({ title, children, onClose, wide }) {
  return (
    <div className="modal-back" onClick={onClose} role="presentation">
      <div
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <span id="modal-title">{title}</span>
          <button
            type="button"
            className="btn btn-sm"
            onClick={onClose}
            aria-label={`Close ${title}`}
          >
            Close
          </button>
        </header>
        <div className="body">{children}</div>
      </div>
    </div>
  );
}

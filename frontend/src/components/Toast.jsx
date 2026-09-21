export default function Toast({ title, detail }) {
  return (
    <div className="toast">
      <strong>{title}</strong>
      {detail ? <span>{detail}</span> : null}
    </div>
  );
}

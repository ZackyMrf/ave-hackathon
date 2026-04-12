export default function Sparkline({ points = [] }) {
  if (!points.length) return <div className="spark-empty">no trend</div>;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1 || 1)) * 100;
      const y = 38 - ((p - min) / range) * 32;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');

  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="sparkline" aria-hidden="true">
      <defs>
        <linearGradient id="sparkFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="rgba(71, 240, 255, 0.5)" />
          <stop offset="100%" stopColor="rgba(71, 240, 255, 0)" />
        </linearGradient>
      </defs>
      <path d={`${d} L 100 40 L 0 40 Z`} fill="url(#sparkFill)" />
      <path d={d} fill="none" stroke="#4bf0ff" strokeWidth="1.4" />
    </svg>
  );
}

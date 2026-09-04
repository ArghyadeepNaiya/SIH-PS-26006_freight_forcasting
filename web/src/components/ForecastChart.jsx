import { useMemo } from 'react';

const W = 880;
const H = 250;
const P = 46;
const FORECAST_WIDTH = 70;

/* Rate history with the forecast cone drawn on the end of it.

   The SVG is labelled but carries no detail, and the figure caption below states the
   same numbers in words. Nothing in this component is available only to someone who
   can see the picture. */
export default function ForecastChart({ points, forecast }) {
  const geometry = useMemo(() => {
    if (!points?.length || !forecast) return null;

    const values = points
      .map((p) => p.value)
      .concat([forecast.lower, forecast.upper, forecast.point]);
    const min = Math.min(...values) * 0.94;
    const max = Math.max(...values) * 1.06;
    const n = points.length;

    const x = (i) => P + (i / (n - 1)) * (W - P - FORECAST_WIDTH - 12);
    const y = (v) => H - 28 - ((v - min) / (max - min)) * (H - 52);

    const line = points
      .map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`)
      .join('');

    const x0 = x(n - 1);
    const x1 = W - 12;
    const band = `M${x0},${y(forecast.current)} L${x1},${y(forecast.upper)} L${x1},${y(
      forecast.lower
    )} Z`;

    const ticks = [0, 1, 2, 3, 4].map((i) => {
      const v = min + ((max - min) * i) / 4;
      return { value: Math.round(v), y: y(v) };
    });

    return { line, band, ticks, x0, x1, yCurrent: y(forecast.current), yPoint: y(forecast.point) };
  }, [points, forecast]);

  if (!geometry) return <p className="empty">Loading rate history.</p>;

  // Amber when the model has no skill, so the colour never contradicts the words.
  const colour = forecast.has_skill ? '#5b9bff' : '#e0a72c';
  const first = points[0].date;
  const last = points[points.length - 1].date;

  return (
    <figure>
      <svg
        className="chart"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Rate history for ${forecast.index_key} with a widening forecast band. The figures are given in full below the chart.`}
      >
        {geometry.ticks.map((t) => (
          <g key={t.value}>
            <line x1={P} y1={t.y} x2={geometry.x1} y2={t.y} stroke="#262b36" />
            <text x="6" y={t.y + 4} fill="#a8b0c2" fontSize="10">
              {t.value}
            </text>
          </g>
        ))}
        <path d={geometry.band} fill={colour} opacity="0.18" />
        <path d={geometry.line} fill="none" stroke="#5b9bff" strokeWidth="1.6" />
        <line
          x1={geometry.x0}
          y1="20"
          x2={geometry.x0}
          y2={H - 28}
          stroke="#a8b0c2"
          strokeDasharray="3,3"
        />
        <line
          x1={geometry.x0}
          y1={geometry.yCurrent}
          x2={geometry.x1}
          y2={geometry.yPoint}
          stroke={colour}
          strokeWidth="1.6"
          strokeDasharray="5,3"
        />
        <text x={geometry.x0 + 6} y="16" fill="#a8b0c2" fontSize="10">
          plus {forecast.horizon_days} day forecast
        </text>
        <text x={P} y={H - 8} fill="#a8b0c2" fontSize="10">
          {first}
        </text>
        <text x={geometry.x1 - 60} y={H - 8} fill="#a8b0c2" fontSize="10">
          {last}
        </text>
      </svg>

      <figcaption>
        {forecast.index_key} is now <b>{forecast.current}</b>. The{' '}
        {forecast.horizon_days} day point forecast is <b>{forecast.point}</b>, with an
        eighty percent band from <b>{forecast.lower}</b> to <b>{forecast.upper}</b>.{' '}
        {forecast.note ? (
          <span style={{ color: '#ffce6b' }}>{forecast.note}</span>
        ) : (
          `Skill score ${forecast.skill_score > 0 ? '+' : ''}${forecast.skill_score}.`
        )}{' '}
        History runs from {first} to {last}.
      </figcaption>
    </figure>
  );
}

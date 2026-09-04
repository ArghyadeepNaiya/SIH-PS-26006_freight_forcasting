/* The single answer the planner came for. Action, reason, and the drivers behind it. */
export default function RecommendationBanner({ recommendation }) {
  if (!recommendation) return null;
  const { action, headline, reason, drivers = [], confidence_label } = recommendation;

  return (
    <section className={`rec ${action}`} aria-labelledby="rec-h">
      <h2 id="rec-h" style={{ margin: 0 }}>
        {headline}
      </h2>
      <p>{reason}</p>
      <ul className="drivers">
        {drivers.map((d) => (
          <li className="chip" key={d}>
            {d}
          </li>
        ))}
        <li className="chip">{confidence_label}</li>
      </ul>
    </section>
  );
}

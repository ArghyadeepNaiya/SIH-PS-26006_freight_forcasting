import { signed } from '../lib/format.js';

/* Whether the forecaster actually beats assuming no change, stated per index and per
   horizon. The decision engine refuses to recommend waiting wherever skill is absent,
   so this panel is the honest counterweight to the forecast chart above it. */
export default function SkillPanel({ rows }) {
  if (!rows?.length) return <p className="empty">Loading skill scores.</p>;

  const withoutSkill = rows.filter((r) => !r.has_skill).length;

  return (
    <>
      <div className="warnbox" role="status">
        {withoutSkill === rows.length ? (
          <>
            <b>No forecasting skill at any horizon on the current dataset.</b> This is
            the correct result while running on scaffolding data, which is generated as
            a near random walk and therefore contains no signal to find. The decision
            engine is hard wired to refuse a wait recommendation whenever skill is
            absent, so the system falls back to fix now and says why. Load real index
            history into <code>data/raw/baltic_indices.csv</code> to obtain the real
            answer.
          </>
        ) : (
          <>
            {withoutSkill} of {rows.length} horizons show no skill. The decision engine
            will not recommend waiting at those horizons.
          </>
        )}
      </div>

      <ol className="stack">
        {rows.map((r) => (
          <li key={`${r.index_key}-${r.horizon_days}`}>
            <article className="card" style={{ marginBottom: 0 }}>
              <h3>
                {r.index_key} at {r.horizon_days} days.{' '}
                <span className={r.has_skill ? 'pos' : 'neg'}>
                  {r.has_skill ? 'Has skill' : 'No skill'}
                </span>
              </h3>
              <ul className="facts">
                <li>
                  <span>Model mean absolute error</span>
                  <b>{r.model_mae}</b>
                </li>
                <li>
                  <span>Naive mean absolute error</span>
                  <b>{r.baseline_mae}</b>
                </li>
                <li>
                  <span>Skill score</span>
                  <b className={r.skill_score > 0 ? 'pos' : 'neg'}>
                    {signed(r.skill_score)}
                  </b>
                </li>
              </ul>
            </article>
          </li>
        ))}
      </ol>
    </>
  );
}

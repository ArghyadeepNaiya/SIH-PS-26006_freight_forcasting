/* Every editable number the cost model runs on, with the provenance of each one.
   A figure whose source begins with the word ASSUMPTION has not been verified against
   a published rate, and this panel says so rather than hiding it. */
export default function AssumptionsPanel({ assumptions }) {
  const entries = Object.entries(assumptions ?? {});
  if (!entries.length) return <p className="empty">Loading assumptions.</p>;

  const unverified = entries.filter(([, a]) =>
    String(a.source).toUpperCase().includes('ASSUMPTION')
  ).length;

  return (
    <section aria-labelledby="assume-h">
      <h2 id="assume-h">Cost assumptions</h2>
      <p className="sub">
        {entries.length} figures drive the cost model. {unverified} of them are still
        unverified assumptions. All of them are editable in{' '}
        <code>data/reference/cost_assumptions.json</code>.
      </p>

      <ol className="stack">
        {entries.map(([key, a]) => (
          <li key={key}>
            <article className="card" style={{ marginBottom: 0 }}>
              <h3>{key.replace(/_/g, ' ')}</h3>
              <ul className="facts">
                <li>
                  <span>Value</span>
                  <b>
                    {a.value} {a.unit}
                  </b>
                </li>
                <li>
                  <span>Editable</span>
                  <b>{a.editable ? 'Yes' : 'No'}</b>
                </li>
              </ul>
              <p className="cite">Source: {a.source}</p>
            </article>
          </li>
        ))}
      </ol>
    </section>
  );
}

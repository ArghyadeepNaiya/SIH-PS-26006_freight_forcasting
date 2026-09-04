import AssumptionsPanel from '../components/AssumptionsPanel.jsx';
import { tonnes } from '../lib/format.js';

/* The physical limits that decide which ships can call where. These are the numbers
   the constraint engine reads, shown exactly as it reads them, with the citation for
   the draft figure because draft is what rules most candidates out. */
export default function PortIntelligence({ reference }) {
  if (!reference) return <p className="empty">Loading reference data.</p>;

  const ports = reference.ports ?? [];

  return (
    <>
      <h2>East Coast discharge ports</h2>
      <p className="sub">
        {ports.length} ports. Every figure below is read straight from{' '}
        <code>data/reference/ports.json</code>.
      </p>

      <ol className="stack">
        {ports.map((p) => {
          const citations = p.citations ?? {};
          const assumed = Object.values(citations).filter((v) =>
            String(v).toUpperCase().includes('ASSUMPTION')
          ).length;

          return (
            <li key={p.code}>
              <article className="card" style={{ marginBottom: 0 }}>
                <h3>
                  {p.name}. {p.state}, code {p.code}
                </h3>
                <ul className="facts">
                  <li>
                    <span>Maximum draft</span>
                    <b>{p.max_draft_m} metres</b>
                  </li>
                  <li>
                    <span>Maximum length overall</span>
                    <b>{p.max_loa_m} metres</b>
                  </li>
                  <li>
                    <span>Maximum beam</span>
                    <b>{p.max_beam_m} metres</b>
                  </li>
                  <li>
                    <span>Maximum deadweight</span>
                    <b>{tonnes(p.max_dwt)} tonnes</b>
                  </li>
                  <li>
                    <span>Lightering available</span>
                    <b>{p.lightering_available ? 'Yes' : 'No'}</b>
                  </li>
                  <li>
                    <span>Typical wait</span>
                    <b>{p.typical_wait_days} days</b>
                  </li>
                </ul>
                <p className="cite">
                  Draft source: {citations.max_draft_m || 'none recorded'}
                </p>
                {assumed > 0 && (
                  <p className="assume">
                    {assumed} field{assumed === 1 ? '' : 's'} on this port{' '}
                    {assumed === 1 ? 'is' : 'are'} still an unverified assumption.
                  </p>
                )}
              </article>
            </li>
          );
        })}
      </ol>

      <AssumptionsPanel assumptions={reference.assumptions} />
    </>
  );
}

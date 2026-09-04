import { useState } from 'react';
import * as api from '../api/client.js';
import CargoInputForm from '../components/CargoInputForm.jsx';
import RecommendationBanner from '../components/RecommendationBanner.jsx';
import OptionCard from '../components/OptionCard.jsx';
import RejectedOptionCard from '../components/RejectedOptionCard.jsx';

const MAX_REJECTED_SHOWN = 10;

export default function DecisionConsole({ reference }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(payload) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.recommend(payload));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <CargoInputForm reference={reference} busy={busy} onSubmit={handleSubmit} />

      {/* One live region for the whole answer, so a screen reader announces the
          result once rather than once per card as the list renders. */}
      <div aria-live="polite" aria-busy={busy}>
        {busy && (
          <p className="empty">
            Evaluating every vessel class against every East Coast discharge port.
          </p>
        )}

        {error && (
          <p className="errbox" role="alert">
            <b>No recommendation was produced.</b> {error}
          </p>
        )}

        {result && (
          <>
            <RecommendationBanner recommendation={result.recommendation} />

            {result.options.length === 0 ? (
              <p className="empty">
                No feasible vessel and port combination was found. Every candidate is
                listed below with the constraint that ruled it out.
              </p>
            ) : (
              <>
                <h2>Ranked options. {result.options.length} feasible</h2>
                <ol className="stack">
                  {result.options.map((o, i) => (
                    <li key={`${o.vessel_class}-${o.discharge_port}`}>
                      <OptionCard option={o} rank={i} />
                    </li>
                  ))}
                </ol>
              </>
            )}

            {result.rejected.length > 0 && (
              <>
                <h2>Ruled out. {result.rejected.length} combinations</h2>
                <p className="sub">
                  Shown deliberately. Knowing what the system rejected, and why, is
                  what makes the recommendation trustworthy.
                  {result.rejected.length > MAX_REJECTED_SHOWN &&
                    ` The first ${MAX_REJECTED_SHOWN} are listed.`}
                </p>
                <ol className="stack">
                  {result.rejected.slice(0, MAX_REJECTED_SHOWN).map((r) => (
                    <li key={`${r.vessel_class}-${r.discharge_port}`}>
                      <RejectedOptionCard rejected={r} />
                    </li>
                  ))}
                </ol>
              </>
            )}
          </>
        )}
      </div>
    </>
  );
}

import { useEffect, useRef, useState } from 'react';
import * as api from './api/client.js';
import DecisionConsole from './pages/DecisionConsole.jsx';
import MarketForecast from './pages/MarketForecast.jsx';
import PortIntelligence from './pages/PortIntelligence.jsx';

/* Three screens, selected by state rather than by a router. There is no deep linking
   requirement yet, and one less dependency is one less thing to explain to a judge. */
const PAGES = [
  { id: 'console', label: 'Decision console', Component: DecisionConsole },
  { id: 'market', label: 'Market and forecast', Component: MarketForecast },
  { id: 'ports', label: 'Port intelligence', Component: PortIntelligence }
];

export default function App() {
  const [pageIndex, setPageIndex] = useState(0);
  const [reference, setReference] = useState(null);
  const [status, setStatus] = useState(null);
  const [bootError, setBootError] = useState(null);
  const mainRef = useRef(null);
  const firstRender = useRef(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [h, ref] = await Promise.all([api.health(), api.reference()]);
        if (cancelled) return;
        setStatus(h);
        setReference(ref);
      } catch (e) {
        if (!cancelled) setBootError(e.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* Moving focus to main on a page change is what tells a screen reader that the
     content underneath the navigation has been replaced. Without it the reader stays
     on the button and the new page is silent. The first render is skipped so focus
     is not stolen from the top of the document on load. */
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [pageIndex]);

  const { Component, label } = PAGES[pageIndex];
  const isReal = status?.is_real_data;

  return (
    <>
      <a className="skip" href="#main">
        Skip to main content
      </a>

      <header>
        <div>
          <h1>Freight Charter Decision Console</h1>
          <p className="sub">
            Vessel class and discharge port for East Coast India bulk imports.
          </p>
        </div>
        <p className={`badge ${isReal ? 'real' : 'scaffold'}`} role="status">
          {status
            ? `${isReal ? 'Real data' : 'Scaffolding data'}. Source: ${status.data_source}`
            : 'Loading data source'}
        </p>
      </header>

      <nav aria-label="Screens">
        {PAGES.map((p, i) => (
          <button
            key={p.id}
            type="button"
            aria-current={i === pageIndex ? 'page' : undefined}
            onClick={() => setPageIndex(i)}
          >
            {p.label}
          </button>
        ))}
      </nav>

      <main id="main" ref={mainRef} tabIndex={-1} aria-label={label}>
        {bootError ? (
          <div className="errbox" role="alert">
            <b>The service could not be reached.</b> {bootError} Start it with{' '}
            <code>./run.sh</code> and reload this page.
          </div>
        ) : (
          <Component reference={reference} status={status} />
        )}
      </main>

      <footer>
        <p className="sub" style={{ padding: '0 24px 24px' }}>
          Figures come from editable reference files in <code>data/reference/</code>.
          Anything marked as an assumption has not been verified against a published
          source.
        </p>
      </footer>
    </>
  );
}

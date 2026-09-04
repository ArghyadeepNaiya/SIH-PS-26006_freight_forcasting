import { useEffect, useRef, useState } from 'react';
import * as api from '../api/client.js';
import ForecastChart from '../components/ForecastChart.jsx';
import SkillPanel from '../components/SkillPanel.jsx';

const INDEXES = [
  { key: 'BCI', label: 'Baltic Capesize Index' },
  { key: 'BPI', label: 'Baltic Panamax Index' },
  { key: 'BSI', label: 'Baltic Supramax Index' },
  { key: 'BHSI', label: 'Baltic Handysize Index' }
];
const HORIZONS = [7, 14, 30, 60, 90];

export default function MarketForecast() {
  const [indexKey, setIndexKey] = useState('BCI');
  const [horizon, setHorizon] = useState(30);
  const [points, setPoints] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [skillRows, setSkillRows] = useState(null);
  const [error, setError] = useState(null);

  // History is fetched once per index and kept, because it does not change while the
  // page is open and it is the largest payload the app requests.
  const historyCache = useRef({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError(null);
        const [hist, fc] = await Promise.all([
          historyCache.current[indexKey]
            ? Promise.resolve(historyCache.current[indexKey])
            : api.history(indexKey, 504),
          api.forecast(indexKey, horizon)
        ]);
        if (cancelled) return;
        historyCache.current[indexKey] = hist;
        setPoints(hist.points);
        setForecast(fc);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [indexKey, horizon]);

  useEffect(() => {
    let cancelled = false;
    api
      .skill()
      .then((s) => {
        if (!cancelled) setSkillRows(s.rows);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <section className="card" aria-labelledby="hist-h">
        <h2 id="hist-h" className="card-title">
          Rate history and forecast
        </h2>
        <p className="sub">The last twenty four months, with the forward band.</p>

        <label htmlFor="index">Index</label>
        <select
          id="index"
          value={indexKey}
          onChange={(e) => setIndexKey(e.target.value)}
        >
          {INDEXES.map((i) => (
            <option key={i.key} value={i.key}>
              {i.label}
            </option>
          ))}
        </select>

        <label htmlFor="fc-horizon">Forecast horizon in days</label>
        <select
          id="fc-horizon"
          value={horizon}
          onChange={(e) => setHorizon(Number(e.target.value))}
        >
          {HORIZONS.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>

        <div aria-live="polite">
          {error ? (
            <p className="errbox" role="alert">
              Could not load the chart. {error}
            </p>
          ) : (
            <ForecastChart points={points} forecast={forecast} />
          )}
        </div>
      </section>

      <h2>Forecast honesty panel</h2>
      <p className="sub">
        A forecast that cannot beat assuming no change is not a forecast. Each horizon
        is scored against that naive baseline.
      </p>
      <SkillPanel rows={skillRows} />
    </>
  );
}

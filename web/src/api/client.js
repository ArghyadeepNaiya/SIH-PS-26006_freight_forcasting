/* Single door to the ML service. Every network call in the app goes through here,
   so error handling and the base URL are defined in exactly one place. */

// Empty by default. The Vite dev server proxies /ml to FastAPI, so relative paths
// stay same origin. Set VITE_API_BASE when the API lives on another host.
const BASE = import.meta.env.VITE_API_BASE || '';

/* FastAPI returns 422 with a list of field errors. Turn that into one readable
   sentence rather than showing the raw pydantic structure to a planner. */
function readError(body, status) {
  if (!body) return `Request failed with status ${status}.`;
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail
      .map((e) => {
        const loc = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : 'input';
        return `${loc}: ${e.msg}`;
      })
      .join('. ');
  }
  return `Request failed with status ${status}.`;
}

async function getJSON(path, options) {
  const res = await fetch(BASE + path, options);
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) throw new Error(readError(body, res.status));
  return body;
}

export const health = () => getJSON('/ml/health');

export const reference = () => getJSON('/ml/reference');

export const history = (indexKey, days = 504) =>
  getJSON(`/ml/history?index_key=${encodeURIComponent(indexKey)}&days=${days}`);

export const forecast = (indexKey, horizonDays) =>
  getJSON(
    `/ml/forecast?index_key=${encodeURIComponent(indexKey)}&horizon_days=${horizonDays}`
  );

export const skill = () => getJSON('/ml/skill');

export const recommend = (payload) =>
  getJSON('/ml/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

import { useEffect, useMemo, useState } from 'react';

const HORIZONS = [7, 14, 30, 60, 90];

/* The cargo list is driven by the origin, because an origin only supplies certain
   cargoes. Sending a pair the routes file does not contain returns a 400 from the
   pipeline, so the invalid combination is never offered in the first place. */
export default function CargoInputForm({ reference, busy, onSubmit }) {
  const origins = reference?.origins ?? [];
  const cargoTypes = reference?.cargo_types ?? [];
  const plants = reference?.plants ?? [];

  const [origin, setOrigin] = useState('');
  const [cargo, setCargo] = useState('');
  const [quantity, setQuantity] = useState(75000);
  const [plant, setPlant] = useState('');
  const [horizon, setHorizon] = useState(30);
  const [formError, setFormError] = useState(null);

  const cargoByCode = useMemo(
    () => Object.fromEntries(cargoTypes.map((c) => [c.code, c])),
    [cargoTypes]
  );

  const selectedOrigin = origins.find((o) => o.code === origin);
  const allowedCargo = selectedOrigin?.cargo ?? [];
  const selectedCargo = cargoByCode[cargo];

  // Pick the first origin as soon as reference data arrives.
  useEffect(() => {
    if (!origin && origins.length) setOrigin(origins[0].code);
  }, [origins, origin]);

  // Keep the cargo selection valid for the chosen origin, preserving it where possible.
  useEffect(() => {
    if (!allowedCargo.length) return;
    if (!allowedCargo.includes(cargo)) setCargo(allowedCargo[0]);
  }, [allowedCargo, cargo]);

  const ready = reference && origin && cargo;

  function handleSubmit(event) {
    event.preventDefault();
    if (!ready) {
      setFormError(
        'Reference data has not loaded yet. Wait for the origin and cargo lists to fill, then try again.'
      );
      return;
    }
    if (!(Number(quantity) > 0)) {
      setFormError('Enter a quantity greater than zero.');
      return;
    }
    setFormError(null);
    onSubmit({
      cargo_type: cargo,
      quantity_tonnes: Number(quantity),
      origin,
      destination_plant: plant || null,
      horizon_days: Number(horizon)
    });
  }

  return (
    <section className="card" aria-labelledby="cargo-h">
      <h2 id="cargo-h" className="card-title">
        Cargo requirement
      </h2>
      <p className="sub">Describe the parcel. Every field has a sensible default.</p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="origin">Load origin</label>
        <select
          id="origin"
          value={origin}
          aria-describedby="origin-hint"
          onChange={(e) => setOrigin(e.target.value)}
        >
          {origins.map((o) => (
            <option key={o.code} value={o.code}>
              {o.name}
            </option>
          ))}
        </select>
        <p className="hint" id="origin-hint">
          Cargo choices update to match what this origin supplies.
        </p>

        <label htmlFor="cargo">Cargo type</label>
        <select
          id="cargo"
          value={cargo}
          aria-describedby="cargo-hint"
          onChange={(e) => setCargo(e.target.value)}
        >
          {allowedCargo.map((code) => (
            <option key={code} value={code}>
              {cargoByCode[code]?.name ?? code}
            </option>
          ))}
        </select>
        <p className="hint" id="cargo-hint">
          {selectedCargo
            ? `Stowage factor ${selectedCargo.stowage_factor_m3_per_t} cubic metres per tonne. Handling runs at ${selectedCargo.handling_rate_multiplier} times the port norm.`
            : 'Stowage and handling figures appear once a cargo is chosen.'}
        </p>

        <label htmlFor="qty">Quantity in tonnes</label>
        <input
          id="qty"
          type="number"
          min="1000"
          step="5000"
          required
          value={quantity}
          aria-describedby="qty-hint"
          onChange={(e) => setQuantity(e.target.value)}
        />
        <p className="hint" id="qty-hint">
          Total parcel size required at the plant.
        </p>

        <label htmlFor="plant">Destination plant</label>
        <select id="plant" value={plant} onChange={(e) => setPlant(e.target.value)}>
          <option value="">Let the system choose the port</option>
          {plants.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>

        <label htmlFor="horizon">Decision horizon in days</label>
        <select
          id="horizon"
          value={horizon}
          onChange={(e) => setHorizon(Number(e.target.value))}
        >
          {HORIZONS.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>

        {formError && (
          <p className="errbox" role="alert" style={{ marginTop: 16 }}>
            {formError}
          </p>
        )}

        <button className="go" type="submit" disabled={busy}>
          {busy ? 'Computing' : 'Get recommendation'}
        </button>
      </form>
    </section>
  );
}

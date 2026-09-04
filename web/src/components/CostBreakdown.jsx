import { money, tonnes } from '../lib/format.js';

/* Every dollar in the landed cost, itemised, plus the two capacity ceilings and which
   of them actually bound. A number a planner cannot take apart is a number they will
   not trust. Written as a list rather than a table so it reads linearly aloud. */
export default function CostBreakdown({ option }) {
  const b = option.cost_breakdown_usd_per_tonne;
  const t = option.time_breakdown_days;

  return (
    <>
      <ul className="bdlist">
        <li>
          <span>Freight, hire plus ballast allowance</span>
          <b>{money(b.freight)} per tonne</b>
        </li>
        <li>
          <span>Expected demurrage, {t.waiting} day wait</span>
          <b>{money(b.expected_demurrage)} per tonne</b>
        </li>
        <li>
          <span>Port charges</span>
          <b>{money(b.port_charges)} per tonne</b>
        </li>
        <li>
          <span>
            Lightering
            {option.lightered_tonnes
              ? `, ${tonnes(option.lightered_tonnes)} tonnes`
              : ''}
          </span>
          <b>{money(b.lightering)} per tonne</b>
        </li>
        <li>
          <span>
            Inland movement to plant
            {option.inland_km ? `, ${option.inland_km} km` : ''}
          </span>
          <b>{money(b.inland)} per tonne</b>
        </li>
        <li className="total">
          <span>Landed cost per tonne</span>
          <b>{money(option.landed_cost_usd_per_tonne)} per tonne</b>
        </li>
      </ul>

      <ul className="bdlist" style={{ marginTop: 14 }}>
        <li>
          <span>Weight ceiling, from draft and deadweight</span>
          <b>{tonnes(option.weight_capacity_tonnes)} tonnes</b>
        </li>
        <li>
          <span>
            Volume ceiling
            {option.grain_capacity_m3
              ? `, ${tonnes(option.grain_capacity_m3)} cubic metres of hold at ${option.stowage_factor_m3_per_t} cubic metres per tonne`
              : ', not modelled'}
          </span>
          <b>
            {option.volume_capacity_tonnes
              ? `${tonnes(option.volume_capacity_tonnes)} tonnes`
              : 'Not available'}
          </b>
        </li>
        <li>
          <span>Which ceiling binds</span>
          <b>
            {option.cubes_out
              ? 'Volume. The cargo cubes out.'
              : 'Weight. The cargo weighs out.'}
          </b>
        </li>
      </ul>

      <p className="assume">
        {option.cubes_out
          ? `This cargo fills the holds before the ship reaches its deadweight, so ${tonnes(
              option.nominal_capacity_tonnes - option.deliverable_tonnes
            )} tonnes of carrying capacity is unusable. Lightering cannot help, because hold space is fixed.`
          : `Binding constraint is the ${option.binding_constraint} draft of ${option.binding_draft_m} metres against a vessel laden draft of ${option.vessel_laden_draft_m} metres.`}{' '}
        Handling runs at {Number(option.cargo_handling_multiplier).toFixed(2)} times the
        port norm for this cargo. Cost figures use editable assumptions from
        cost_assumptions.json, and stowage figures from cargo_types.json.
      </p>
    </>
  );
}

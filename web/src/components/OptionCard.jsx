import CostBreakdown from './CostBreakdown.jsx';
import { inr, money, perDay, tonnes } from '../lib/format.js';

/* One feasible vessel and port pairing. The headline number is the landed cost per
   tonne, because that is the only figure that lets two different vessel classes be
   compared honestly. */
export default function OptionCard({ option, rank }) {
  const isBest = rank === 0;

  return (
    <article className={`opt ${isBest ? 'best' : ''}`}>
      <h3>
        {isBest && <span className="rank">Best</span>}
        {option.vessel_class} to {option.discharge_port}
      </h3>
      <p className="opt-sub">{option.reason}</p>

      <p className="price">
        <span className="amt">{money(option.landed_cost_usd_per_tonne)}</span>
        <span className="unit">per tonne delivered</span>
        <span className="unit">{inr(option.landed_cost_inr_per_tonne)} per tonne</span>
      </p>

      <ul className="meta">
        <li>
          Delivers <b>{tonnes(option.deliverable_tonnes)} tonnes</b> of{' '}
          {tonnes(option.nominal_capacity_tonnes)} tonnes capacity
        </li>
        <li>
          Load <b>{option.load_percentage} percent</b>
        </li>
        <li>
          Voyage <b>{option.total_days} days</b>
        </li>
        <li>
          Time charter equivalent <b>{perDay(option.tce_usd_per_day)} per day</b>
        </li>
        {option.cubes_out && <li className="flag-cube">Cubes out</li>}
      </ul>

      <details className="bd">
        <summary>Show cost breakdown and assumptions</summary>
        <CostBreakdown option={option} />
      </details>
    </article>
  );
}

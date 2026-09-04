/* Number formatting used across the pages. Kept together so a change to the way
   money is written happens once, not in eight components. */

export const money = (n) => `$${Number(n).toFixed(2)}`;

export const inr = (n) => `₹${Math.round(Number(n)).toLocaleString('en-IN')}`;

export const tonnes = (n) => Number(n).toLocaleString('en-IN');

export const perDay = (n) => `$${Number(n).toLocaleString('en-US')}`;

export const signed = (n, places = 4) =>
  `${Number(n) > 0 ? '+' : ''}${Number(n).toFixed(places)}`;

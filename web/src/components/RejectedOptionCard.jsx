/* A combination the engine threw away, with the constraint that killed it and the
   source that constraint came from. Showing the rejects is what makes the accepted
   answer believable. */
export default function RejectedOptionCard({ rejected }) {
  return (
    <article className="rej">
      <h3 style={{ margin: 0 }}>
        {rejected.vessel_class} to {rejected.discharge_port}
        <span className="tag">{rejected.failed_constraint}</span>
      </h3>
      <p>{rejected.explanation}</p>
      <p className="cite">Source: {rejected.source_citation}</p>
    </article>
  );
}

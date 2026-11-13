import type { ReactNode } from "react";
import type { Handover as HandoverData } from "./run";

const zurich = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Zurich",
  });

function Row(props: Readonly<{ name: string; children: ReactNode }>) {
  return (
    <div>
      <dt>{props.name}</dt>
      <dd>{props.children}</dd>
    </div>
  );
}

function List(props: Readonly<{ items: ReactNode[]; none: string }>) {
  if (props.items.length === 0) return <>{props.none}</>;
  return (
    <ul>
      {props.items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

function device(data: HandoverData): string {
  if (!data.device) return "None on record";
  const model = data.device.model ? `, ${data.device.model}` : "";
  return data.device.id + model;
}

/** What the receiving team gets with an escalation. Code fills in the facts, and
 * FirstLine writes only its notes, so the page says which is which. */
export function Handover({ data }: Readonly<{ data: HandoverData }>) {
  const who = data.requester;
  const sla = data.sla ?? "No SLA on record";
  return (
    <section className="handover" aria-labelledby="handover-title">
      <h3 id="handover-title">Handover to {data.queue}</h3>
      <div className="handover-part">
        <p className="handover-by">FirstLine&apos;s notes</p>
        <dl>
          <Row name="Likely cause">{data.cause || "Unknown"}</Row>
          <Row name="Ruled out">{data.ruled_out || "Nothing stated"}</Row>
          <Row name="Next step">{data.next_step || "Nothing stated"}</Row>
        </dl>
      </div>
      <div className="handover-part">
        <p className="handover-by">
          From the records and lookups, filled in by code
        </p>
        <dl>
          <Row name="Requester">
            {who
              ? `${who.id}, ${who.department ?? "?"}, ${who.office ?? "?"}`
              : "Not named"}
          </Row>
          <Row name="Device">{device(data)}</Row>
          <Row name="Priority and SLA">
            {data.priority}, {sla}
            {data.deadline && (
              <span className="detail-sub">
                Due {zurich(data.deadline)}, Zürich time
              </span>
            )}
          </Row>
          <Row name="Applications">
            {data.applications.length > 0
              ? data.applications.join(", ")
              : "None named"}
          </Row>
          <Row name="Checks">
            <List
              items={data.checks.map((c) => (
                <>
                  <code>{c.step}</code> {c.result}
                </>
              ))}
              none="None with a recorded result"
            />
          </Row>
          <Row name="Similar incidents">
            {data.similar.length > 0 ? (
              <code>{data.similar.join(", ")}</code>
            ) : (
              "None looked up"
            )}
          </Row>
          <Row name="Still unknown">
            <List items={data.unknown} none="Nothing" />
          </Row>
        </dl>
      </div>
    </section>
  );
}

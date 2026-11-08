// POST /api/agreement: step 2. The person signs the lead generation agreement (typed name, their email, the box).
// One new Signups row holds the signature: who, when, from where, which version. Returns the row for the next steps.
import { json, rich, notion, EMAIL, off, OFF } from "../../lib/notion.js";

export const VERSION = "2026-11-08-flat";

export async function onRequestPost({ request, env }) {
  if (off(env)) return json(503, OFF);
  let b;
  try { b = await request.json(); } catch { return json(400, { error: "Send the form as JSON." }); }
  const name = String(b.name || "").trim().slice(0, 120);
  const email = String(b.email || "").trim().toLowerCase().slice(0, 200);
  const problems = [];
  if (name.split(/\s+/).length < 2) problems.push("type your full name to sign");
  if (!EMAIL.test(email)) problems.push("add your email");
  if (b.agreed !== true) problems.push("tick the box to agree");
  if (problems.length) return json(400, { error: "Almost there.", problems });

  const signature = { name, email, at: new Date().toISOString(), ip: request.headers.get("cf-connecting-ip") || "",
    agent: (request.headers.get("user-agent") || "").slice(0, 200), version: VERSION };
  const r = await notion(env, "POST", "/pages", {
    parent: { data_source_id: env.RCM_SIGNUPS_DS },
    properties: {
      Name: { title: [{ type: "text", text: { content: name } }] },
      Status: { select: { name: "agreement signed" } },
      Agreement: rich(JSON.stringify(signature)),
      Intake: rich(JSON.stringify({ owner_email: email, owner_full_name: name, owner_first_name: name.split(/\s+/)[0] })),
    },
  });
  if (!r.ok) return json(502, { error: "We couldn't save your signature. Please try again in a moment." });
  return json(200, { ok: true, row: r.data.id });
}

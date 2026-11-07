// POST /api/intake: step 3. The answers the voice intake (or the typed form) gathered, saved on the person's
// Signups row. Only after this does the page offer the deposit, which is the last step.
import { json, rich, notion, textOf, ROW, off, OFF } from "../../lib/notion.js";

export const FIELDS = [
  "business", "website", "sells", "service_area", "crm_kind", "crm_name",
  "old_quotes_count", "old_quotes_sms_consent", "past_customers_count", "past_customers_sms_consent",
  "no_shows_count", "no_shows_sms_consent", "lost_deals_count", "lost_deals_sms_consent", "plays", "notes",
];
const REQUIRED = ["business", "sells", "service_area", "crm_kind"];
const CONSENT = ["yes", "no", "unknown"];

export function check(a) {
  const problems = REQUIRED.filter(k => !String(a[k] ?? "").trim()).map(k => `missing: ${k}`);
  const lists = ["old_quotes", "past_customers", "no_shows", "lost_deals"].filter(l => Number(a[`${l}_count`]) > 0);
  if (!lists.length) problems.push("at least one list, and roughly how many are on it");
  for (const l of lists) if (a[`${l}_sms_consent`] && !CONSENT.includes(a[`${l}_sms_consent`])) problems.push(`${l}: text consent is yes, no or unknown`);
  if (a.website && !String(a.website).startsWith("https://")) problems.push("website must start with https://");
  return problems;
}

export async function onRequestPost({ request, env }) {
  if (off(env)) return json(503, OFF);
  let a;
  try { a = await request.json(); } catch { return json(400, { error: "Send the answers as JSON." }); }
  const row = String(a.row || "");
  if (!ROW.test(row)) return json(400, { error: "Start from the agreement page, so your answers land on your signup." });
  const problems = check(a);
  if (problems.length) return json(400, { error: "A few answers are missing.", problems });

  const page = await notion(env, "GET", `/pages/${row}`);
  const status = page.data?.properties?.Status?.select?.name;
  if (!page.ok || !["agreement signed", "intake done"].includes(status)) {
    return json(400, { error: "We couldn't find your signed agreement. Please start from the agreement page." });
  }
  let base = {};
  try { base = JSON.parse(textOf(page.data.properties.Intake) || "{}"); } catch { base = {}; }
  const answers = Object.fromEntries(FIELDS.filter(k => a[k] !== undefined && a[k] !== "").map(k => [k, a[k]]));
  // The signer's name and email come from the signed agreement; newer answers replace older ones.
  const owner = Object.fromEntries(["owner_email", "owner_full_name", "owner_first_name"].map(k => [k, base[k]]));
  const intake = { ...base, ...answers, ...owner, agreement_accepted: true };
  const r = await notion(env, "PATCH", `/pages/${row}`, { properties: {
    Name: { title: [{ type: "text", text: { content: String(intake.business).slice(0, 200) } }] },
    Status: { select: { name: "intake done" } },
    Intake: rich(JSON.stringify(intake)),
  } });
  if (!r.ok) return json(502, { error: "We couldn't save your answers. Please try again in a moment." });
  return json(200, { ok: true, email: base.owner_email || "" });
}

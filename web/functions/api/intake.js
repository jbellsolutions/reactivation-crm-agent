// POST /api/intake: the intake form after the deposit. Checks the paid Stripe session, then writes one row to
// the Reactivation Signups data source in Notion for the poller (`rcm poll`). Off until its three settings exist.

export const FIELDS = [
  "business", "owner_first_name", "owner_full_name", "owner_email", "website", "sells", "service_area",
  "rep_first_name", "booking_link", "timezone", "qualifying",
  "old_quotes_count", "old_quotes_sms_consent", "past_customers_count", "past_customers_sms_consent",
  "no_shows_count", "no_shows_sms_consent", "lost_deals_count", "lost_deals_sms_consent",
  "crm_kind", "crm_name", "plays", "orgo_path", "has_orgo", "model_provider", "slack",
];
const REQUIRED = ["business", "owner_first_name", "owner_email", "website", "sells", "service_area",
  "booking_link", "timezone", "qualifying", "crm_kind"];
const CHUNK = 1900;

const json = (status, body) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

const rich = text => ({ rich_text: Array.from({ length: Math.ceil(text.length / CHUNK) || 1 },
  (_, i) => ({ type: "text", text: { content: text.slice(i * CHUNK, (i + 1) * CHUNK) } })) });

export function check(form) {
  const problems = REQUIRED.filter(k => !String(form[k] ?? "").trim()).map(k => `missing: ${k}`);
  if (form.owner_email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.owner_email)) problems.push("owner_email isn't an email address");
  for (const k of ["website", "booking_link"]) if (form[k] && !String(form[k]).startsWith("https://")) problems.push(`${k} must start with https://`);
  const lists = ["old_quotes", "past_customers", "no_shows", "lost_deals"].filter(l => Number(form[`${l}_count`]) > 0);
  if (!lists.length) problems.push("add at least one list and roughly how many are on it");
  return problems;
}

export async function onRequestPost({ request, env }) {
  if (!env.STRIPE_READ_KEY || !env.NOTION_TOKEN || !env.RCM_SIGNUPS_DS) {
    return json(503, { error: "Signup isn't switched on yet. Nothing was charged twice; please email justin@usingaitoscale.com." });
  }
  let form;
  try { form = await request.json(); } catch { return json(400, { error: "Send the form as JSON." }); }
  const sid = String(form.session_id || "");
  if (!/^cs_(test|live)_[A-Za-z0-9]+$/.test(sid)) return json(400, { error: "This page needs the link from your deposit receipt." });
  const problems = check(form);
  if (problems.length) return json(400, { error: "A few answers are missing.", problems });

  const s = await fetch(`https://api.stripe.com/v1/checkout/sessions/${sid}`,
    { headers: { Authorization: `Bearer ${env.STRIPE_READ_KEY}` } });
  if (!s.ok) return json(400, { error: "We couldn't find that deposit." });
  const session = await s.json();
  if (session.payment_status !== "paid") return json(400, { error: "That deposit isn't paid yet." });
  const paidBy = String(session.customer_details?.email || "").toLowerCase();
  if (paidBy !== String(form.owner_email).trim().toLowerCase()) {
    return json(400, { error: "Use the same email you paid the deposit with." });
  }

  const intake = Object.fromEntries(FIELDS.filter(k => form[k] !== undefined && form[k] !== "").map(k => [k, form[k]]));
  const row = await fetch("https://api.notion.com/v1/pages", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.NOTION_TOKEN}`, "Notion-Version": "2025-09-03", "Content-Type": "application/json" },
    body: JSON.stringify({
      parent: { data_source_id: env.RCM_SIGNUPS_DS },
      properties: {
        Name: { title: [{ type: "text", text: { content: String(intake.business).slice(0, 200) } }] },
        Status: { select: { name: "new" } },
        "Checkout session": rich(sid),
        Intake: rich(JSON.stringify(intake)),
      },
    }),
  });
  if (!row.ok) return json(502, { error: "We couldn't save your answers. Please try again in a moment." });
  return json(200, { ok: true });
}

// POST /api/paid: step 4, after Stripe's payment page sends the person back. Checks the paid first month ($500) with Stripe and
// marks the signup row the payment belongs to (its client_reference_id) as new, for the poller to onboard.
import { json, rich, notion, stripeSession, ROW, off, OFF } from "../../lib/notion.js";

const FIRST_MONTH_CENTS = 50000;

export async function onRequestPost({ request, env }) {
  if (off(env)) return json(503, OFF);
  let b;
  try { b = await request.json(); } catch { return json(400, { error: "Send JSON." }); }
  const sid = String(b.session_id || "");
  if (!/^cs_(test|live)_[A-Za-z0-9]+$/.test(sid)) return json(400, { error: "This page needs the link from your payment." });
  const s = await stripeSession(env, sid);
  if (!s) return json(400, { error: "We couldn't find that payment." });
  if (s.payment_status !== "paid" || Number(s.amount_total) !== FIRST_MONTH_CENTS) return json(400, { error: "That payment isn't through yet." });
  const row = String(s.client_reference_id || "");
  if (!ROW.test(row)) return json(400, { error: "That payment isn't linked to a signup. Please email justin@usingaitoscale.com." });
  const r = await notion(env, "PATCH", `/pages/${row}`, { properties: {
    Status: { select: { name: "new" } },
    "Checkout session": rich(sid),
  } });
  if (!r.ok) return json(502, { error: "Your payment went through, and we couldn't update your signup. We'll fix it; nothing to do on your side." });
  return json(200, { ok: true });
}

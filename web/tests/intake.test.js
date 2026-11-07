import test from "node:test";
import assert from "node:assert";
import { onRequestPost as agreement } from "../functions/api/agreement.js";
import { onRequestPost as intake, check } from "../functions/api/intake.js";
import { onRequestPost as paid } from "../functions/api/paid.js";

const ENV = { STRIPE_READ_KEY: "rk_test_not_real", NOTION_TOKEN: "ntn_not_real", RCM_SIGNUPS_DS: "signups-ds" };
const ROW = "2a1b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d";
const ANSWERS = { business: "Harbor Test Roofing", sells: "Roof replacement", service_area: "Tampa Bay", crm_kind: "ghl",
  old_quotes_count: "1800", old_quotes_sms_consent: "yes", plays: "reactivation" };

// A stand-in Notion (one Signups row) and Stripe (one session). Records every write.
function world({ status = "agreement signed", session } = {}) {
  const state = { status, props: { Intake: { rich_text: [{ plain_text: JSON.stringify({ owner_email: "dana@example.com", owner_first_name: "Dana", owner_full_name: "Dana Example" }) }] } }, writes: [] };
  globalThis.fetch = async (url, opts = {}) => {
    const body = opts.body ? JSON.parse(opts.body) : null;
    if (url.startsWith("https://api.stripe.com/")) return new Response(JSON.stringify(session || {}), { status: session ? 200 : 404 });
    if (url === "https://api.notion.com/v1/pages" && opts.method === "POST") { state.writes.push(["create", body]); return new Response(JSON.stringify({ id: ROW }), { status: 200 }); }
    if (url === `https://api.notion.com/v1/pages/${ROW}` && opts.method === "GET") {
      return new Response(JSON.stringify({ id: ROW, properties: { ...state.props, Status: { select: { name: state.status } } } }), { status: 200 });
    }
    if (url === `https://api.notion.com/v1/pages/${ROW}` && opts.method === "PATCH") {
      state.writes.push(["update", body]); state.status = body.properties.Status?.select?.name || state.status;
      return new Response("{}", { status: 200 });
    }
    return new Response("{}", { status: 404 });
  };
  return state;
}
const post = (fn, body, env = ENV, headers = {}) => fn({ request: new Request("https://x/api", { method: "POST", body: JSON.stringify(body), headers }), env });

test("signing writes one row with the signature, and returns it", async () => {
  const w = world();
  const r = await post(agreement, { name: "Dana Example", email: "Dana@Example.com", agreed: true }, ENV, { "cf-connecting-ip": "203.0.113.9" });
  assert.equal(r.status, 200);
  assert.equal((await r.json()).row, ROW);
  const props = w.writes[0][1].properties;
  assert.equal(props.Status.select.name, "agreement signed");
  const sig = JSON.parse(props.Agreement.rich_text.map(t => t.text.content).join(""));
  assert.deepEqual([sig.name, sig.email, sig.ip], ["Dana Example", "dana@example.com", "203.0.113.9"]);
});

test("no signature without a full name, an email and the box", async () => {
  world();
  const r = await post(agreement, { name: "Dana", email: "x", agreed: false });
  assert.equal(r.status, 400);
  assert.equal((await r.json()).problems.length, 3);
});

test("answers land on the signed row, and the agreement's email stays the signer's", async () => {
  const w = world();
  const r = await post(intake, { ...ANSWERS, row: ROW, owner_email: "someone-else@example.org" });
  assert.equal(r.status, 200);
  assert.equal((await r.json()).email, "dana@example.com");
  const props = w.writes[0][1].properties;
  assert.equal(props.Status.select.name, "intake done");
  const saved = JSON.parse(props.Intake.rich_text.map(t => t.text.content).join(""));
  assert.equal(saved.owner_email, "dana@example.com");
  assert.equal(saved.agreement_accepted, true);
  assert.equal(saved.business, "Harbor Test Roofing");
});

test("answers without a signed agreement, or without a list, are refused", async () => {
  world({ status: "new" });
  assert.equal((await post(intake, { ...ANSWERS, row: ROW })).status, 400);
  world();
  const r = await post(intake, { ...ANSWERS, row: ROW, old_quotes_count: "0" });
  assert.equal(r.status, 400);
  assert.ok((await r.json()).problems.some(p => p.includes("at least one list")));
});

test("a paid deposit marks its own row new, for the poller", async () => {
  const w = world({ status: "intake done", session: { payment_status: "paid", amount_total: 50000, client_reference_id: ROW } });
  const r = await post(paid, { session_id: "cs_test_abc123" });
  assert.equal(r.status, 200);
  const props = w.writes[0][1].properties;
  assert.equal(props.Status.select.name, "new");
  assert.equal(props["Checkout session"].rich_text[0].text.content, "cs_test_abc123");
});

test("unpaid, the wrong amount, or no signup on the payment is refused", async () => {
  for (const session of [{ payment_status: "unpaid", amount_total: 50000, client_reference_id: ROW },
                         { payment_status: "paid", amount_total: 100, client_reference_id: ROW },
                         { payment_status: "paid", amount_total: 50000 }]) {
    world({ session });
    assert.equal((await post(paid, { session_id: "cs_test_abc123" })).status, 400);
  }
});

test("everything is off until the settings exist", async () => {
  world();
  for (const fn of [agreement, intake, paid]) assert.equal((await post(fn, {}, {})).status, 503);
});

test("check passes the voice answers", () => assert.deepEqual(check(ANSWERS), []));

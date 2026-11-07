import test from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { onRequestPost, check } from "../functions/api/intake.js";

const ex = name => JSON.parse(readFileSync(new URL(`../../examples/synthetic-client/${name}`, import.meta.url)));
const FORM = { ...ex("form-row.json"), session_id: "cs_test_synthetic0001" };
const SESSION = ex("checkout-session.json");
const ENV = { STRIPE_READ_KEY: "rk_test_not_real", NOTION_TOKEN: "ntn_not_real", RCM_SIGNUPS_DS: "signups-ds" };

function stub(session = SESSION, notionOk = true) {
  const calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url, opts });
    if (url.startsWith("https://api.stripe.com/")) return new Response(JSON.stringify(session), { status: 200 });
    if (url === "https://api.notion.com/v1/pages") return new Response("{}", { status: notionOk ? 200 : 500 });
    return new Response("{}", { status: 404 });
  };
  return calls;
}
const post = (body, env = ENV) => onRequestPost({ request: new Request("https://x/api/intake", { method: "POST", body: JSON.stringify(body) }), env });

test("a paid deposit and a complete form write one new Signups row", async () => {
  const calls = stub();
  const r = await post(FORM);
  assert.equal(r.status, 200);
  const write = calls.find(c => c.url === "https://api.notion.com/v1/pages");
  const body = JSON.parse(write.opts.body);
  assert.deepEqual(body.parent, { data_source_id: "signups-ds" });
  assert.equal(body.properties.Status.select.name, "new");
  const intake = JSON.parse(body.properties.Intake.rich_text.map(t => t.text.content).join(""));
  assert.equal(intake.business, "Harbor Test Roofing");
  assert.equal(intake.session_id, undefined);
});

test("off until its settings exist", async () => {
  stub();
  assert.equal((await post(FORM, {})).status, 503);
});

test("unpaid, someone else's email, or a made-up session id is refused", async () => {
  stub({ ...SESSION, payment_status: "unpaid" });
  assert.equal((await post(FORM)).status, 400);
  stub();
  assert.equal((await post({ ...FORM, owner_email: "someone@example.org" })).status, 400);
  const calls = stub();
  assert.equal((await post({ ...FORM, session_id: "../../v1/customers" })).status, 400);
  assert.equal(calls.length, 0);
});

test("missing answers are named, before anything is called", async () => {
  const calls = stub();
  const r = await post({ ...FORM, booking_link: "http://x", old_quotes_count: 0, past_customers_count: 0 });
  assert.equal(r.status, 400);
  const out = await r.json();
  assert.ok(out.problems.some(p => p.includes("booking_link")));
  assert.ok(out.problems.some(p => p.includes("at least one list")));
  assert.equal(calls.length, 0);
});

test("a Notion failure is reported, not hidden", async () => {
  stub(SESSION, false);
  assert.equal((await post(FORM)).status, 502);
});

test("check passes the example form", () => assert.deepEqual(check(FORM), []));

// The few Notion and Stripe calls the signup functions make. Imported by functions/api/*.js; not a route.

export const NOTION = "https://api.notion.com/v1";
const CHUNK = 1900;

export const json = (status, body) => new Response(JSON.stringify(body), {
  status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

export const rich = text => ({ rich_text: Array.from({ length: Math.ceil(String(text).length / CHUNK) || 1 },
  (_, i) => ({ type: "text", text: { content: String(text).slice(i * CHUNK, (i + 1) * CHUNK) } })) });

export const textOf = prop => ((prop && (prop.rich_text || prop.title)) || []).map(t => t.plain_text ?? t.text?.content ?? "").join("");

export async function notion(env, method, path, body) {
  const r = await fetch(NOTION + path, {
    method,
    headers: { Authorization: `Bearer ${env.NOTION_TOKEN}`, "Notion-Version": "2025-09-03", "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
}

export async function stripeSession(env, sid) {
  const r = await fetch(`https://api.stripe.com/v1/checkout/sessions/${sid}`, { headers: { Authorization: `Bearer ${env.STRIPE_READ_KEY}` } });
  return r.ok ? r.json() : null;
}

export const ROW = /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i;
export const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export const off = env => !env.STRIPE_READ_KEY || !env.NOTION_TOKEN || !env.RCM_SIGNUPS_DS;
export const OFF = { error: "Signup isn't switched on yet. Please email justin@usingaitoscale.com." };

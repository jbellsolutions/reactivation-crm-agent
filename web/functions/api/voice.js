// POST /api/voice: opens a GPT-Live voice session for the intake. The browser sends its WebRTC offer; this asks
// OpenAI for the session with our key (the browser never sees it) and returns the answer. Only for a signup that
// has signed the agreement, so a stranger can't open paid sessions.
import { json, notion, ROW } from "../../lib/notion.js";
import { session } from "../../lib/voice.js";

export async function onRequestPost({ request, env }) {
  if (!env.OPENAI_API_KEY || !env.NOTION_TOKEN) return json(503, { error: "Voice isn't switched on yet. Type your answers below." });
  let b;
  try { b = await request.json(); } catch { return json(400, { error: "Send JSON." }); }
  const row = String(b.row || ""), sdp = String(b.sdp || "");
  if (!ROW.test(row)) return json(400, { error: "Start from the agreement page." });
  if (!sdp.startsWith("v=0") || sdp.length > 20000) return json(400, { error: "That isn't a voice connection offer." });
  const page = await notion(env, "GET", `/pages/${row}`);
  const status = page.data?.properties?.Status?.select?.name;
  if (!page.ok || !["agreement signed", "intake done"].includes(status)) return json(403, { error: "Sign the agreement first." });

  const r = await fetch("https://api.openai.com/v1/live/sessions", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.OPENAI_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify(session(sdp)),
  });
  const out = await r.json().catch(() => ({}));
  if (!r.ok || !out.transport?.sdp) return json(502, { error: "Voice couldn't start. Type your answers below." });
  return json(200, { sdp: out.transport.sdp });
}

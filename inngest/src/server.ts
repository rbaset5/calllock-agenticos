import http from "node:http";
import { serve } from "inngest/node";

import { client, functions } from "./index.js";

const port = Number(process.env.PORT || "8288");
const servePath = process.env.INNGEST_SERVE_PATH || "/api/inngest";
const inngestHandler = serve({
  client,
  functions,
  servePath,
});

const server = http.createServer((req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
  if (url.pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: "ok",
      servePath,
      functionCount: functions.length,
      harnessBaseUrlConfigured: Boolean(process.env.HARNESS_BASE_URL),
      eventSecretConfigured: Boolean(process.env.HARNESS_EVENT_SECRET),
      inngestEventKeyConfigured: Boolean(process.env.INNGEST_EVENT_KEY),
      inngestSigningKeyConfigured: Boolean(process.env.INNGEST_SIGNING_KEY),
    }));
    return;
  }
  if (url.pathname === servePath) {
    inngestHandler(req, res);
    return;
  }
  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Inngest server listening on http://0.0.0.0:${port}${servePath}`);
});

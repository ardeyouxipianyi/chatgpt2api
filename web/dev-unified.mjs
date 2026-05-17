import http from "node:http";
import { spawn } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const publicPort = Number(process.env.CHATGPT2API_PUBLIC_PORT || 3000);
const nextPort = Number(process.env.CHATGPT2API_NEXT_PORT || 3001);
const backendOrigin = new URL(process.env.CHATGPT2API_BACKEND_URL || "http://127.0.0.1:8000");
const webDir = dirname(fileURLToPath(import.meta.url));
const apiPrefixes = ["/v1/", "/api/", "/auth/", "/images/", "/image-thumbnails/"];
const apiExact = new Set(["/version"]);

function isBackendPath(url = "") {
  const pathname = new URL(url, `http://127.0.0.1:${publicPort}`).pathname;
  return apiExact.has(pathname) || apiPrefixes.some((prefix) => pathname.startsWith(prefix));
}

function proxyHttp(req, res, target) {
  const headers = { ...req.headers };
  headers.host = req.headers.host || `127.0.0.1:${publicPort}`;
  headers["x-forwarded-host"] = req.headers.host || `127.0.0.1:${publicPort}`;
  headers["x-forwarded-proto"] = "http";

  const proxyReq = http.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      method: req.method,
      path: req.url,
      headers,
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
      proxyRes.pipe(res);
    },
  );
  proxyReq.setTimeout(0);
  proxyReq.on("error", (error) => {
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json; charset=utf-8" });
    }
    res.end(JSON.stringify({ error: { message: error.message || "proxy error" } }));
  });
  req.pipe(proxyReq);
}

function proxyUpgrade(req, socket, head, target) {
  const headers = { ...req.headers };
  headers.host = `${target.hostname}:${target.port}`;
  const proxyReq = http.request({
    protocol: target.protocol,
    hostname: target.hostname,
    port: target.port,
    method: req.method,
    path: req.url,
    headers,
  });
  proxyReq.on("upgrade", (proxyRes, proxySocket, proxyHead) => {
    socket.write(
      `HTTP/${proxyRes.httpVersion} ${proxyRes.statusCode} ${proxyRes.statusMessage}\r\n`
      + Object.entries(proxyRes.headers)
        .flatMap(([key, value]) => Array.isArray(value) ? value.map((item) => [key, item]) : [[key, value]])
        .map(([key, value]) => `${key}: ${value}`)
        .join("\r\n")
      + "\r\n\r\n",
    );
    if (proxyHead.length) socket.write(proxyHead);
    if (head.length) proxySocket.write(head);
    proxySocket.pipe(socket);
    socket.pipe(proxySocket);
  });
  proxyReq.on("error", () => socket.destroy());
  proxyReq.end();
}

const next = spawn(
  "npx",
  ["next", "dev", "--webpack", "-H", "0.0.0.0", "-p", String(nextPort)],
  {
    cwd: webDir,
    stdio: "inherit",
    shell: process.platform === "win32",
    env: {
      ...process.env,
      PORT: String(nextPort),
    },
  },
);

const server = http.createServer((req, res) => {
  req.setTimeout(0);
  res.setTimeout(0);
  if (isBackendPath(req.url)) {
    proxyHttp(req, res, backendOrigin);
    return;
  }
  proxyHttp(req, res, new URL(`http://127.0.0.1:${nextPort}`));
});

server.on("upgrade", (req, socket, head) => {
  proxyUpgrade(req, socket, head, new URL(`http://127.0.0.1:${nextPort}`));
});

server.timeout = 0;
server.keepAliveTimeout = 0;
server.headersTimeout = 0;

server.listen(publicPort, "0.0.0.0", () => {
  console.log(`[unified] http://0.0.0.0:${publicPort} -> web:${nextPort}, api:${backendOrigin.origin}`);
});

function shutdown() {
  server.close();
  next.kill();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

#!/usr/bin/env node
const http = require('http');
const https = require('https');
const { URL } = require('url');
const { SocksProxyAgent } = require('socks-proxy-agent');

const PORT = process.env.PORT || 8787;
const HOST = '127.0.0.1';
const SOCKS_HOST = process.env.SOCKS_HOST || '127.0.0.1';
const SOCKS_PORT = parseInt(process.env.SOCKS_PORT || '12334', 10);
const SOCKS_PROXY = `socks5://${SOCKS_HOST}:${SOCKS_PORT}`;

const agent = new SocksProxyAgent(SOCKS_PROXY);
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, PUT, DELETE',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, Accept, X-Requested-With',
  'Access-Control-Expose-Headers': '*',
  'Access-Control-Max-Age': '86400'
};

function forwardRequest(targetUrl, req, res) {
  let u;
  try { u = new URL(targetUrl); } catch (e) {
    res.writeHead(400, { ...CORS, 'Content-Type':'application/json' });
    res.end(JSON.stringify({ error:'Invalid URL' }));
    return;
  }
  const lib = u.protocol === 'https:' ? https : http;
  const chunks = [];
  req.on('data', chunk => chunks.push(chunk));
  req.on('end', () => {
    const body = Buffer.concat(chunks);
    const headers = {};
    if (req.headers['content-type']) headers['Content-Type'] = req.headers['content-type'];
    if (req.headers['authorization']) headers['Authorization'] = req.headers['authorization'];
    if (req.headers['accept']) headers['Accept'] = req.headers['accept'];
    if (body.length > 0) headers['Content-Length'] = body.length;

    const options = { method: req.method, headers, agent };
    const proxyReq = lib.request(u, options, (proxyRes) => {
      const respHeaders = {
        ...CORS,
        'Content-Type': proxyRes.headers['content-type'] || 'application/json',
        'Cache-Control': 'no-cache'
      };
      res.writeHead(proxyRes.statusCode || 502, respHeaders);
      proxyRes.pipe(res);
    });

    proxyReq.setTimeout(60000, () => {
      proxyReq.destroy();
      res.writeHead(504, { ...CORS, 'Content-Type':'application/json' });
      res.end(JSON.stringify({ error:'Gateway Timeout' }));
    });

    proxyReq.on('error', (err) => {
      res.writeHead(502, { ...CORS, 'Content-Type':'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    });

    if (body.length) proxyReq.write(body);
    proxyReq.end();
  });
}

const server = http.createServer((req, res) => {
  Object.entries(CORS).forEach(([k,v]) => res.setHeader(k,v));
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
  const reqUrl = new URL(req.url, `http://${HOST}:${PORT}`);
  const target = reqUrl.searchParams.get('url');
  if (target) { forwardRequest(target, req, res); return; }
  res.writeHead(200, { 'Content-Type':'text/plain;charset=utf-8' });
  res.end('Codespace Agent proxy running (with timeout)');
});

server.listen(PORT, HOST, () => {
  console.log(`Proxy listening on http://${HOST}:${PORT} via ${SOCKS_PROXY}`);
});
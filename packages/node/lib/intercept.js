const tls = require("tls");
const http2 = require("http2");
const zlib = require("zlib");
const { resolveAwsArn, isArnUrl } = require("./resolve-arn");

let native = null;
let origTlsConnect = null;
let origH2Connect = null;
let patched = false;

function activate(nativeModule) {
  native = nativeModule;
  patch();
}

function deactivate() {
  if (origTlsConnect) {
    tls.connect = origTlsConnect;
    origTlsConnect = null;
  }
  if (origH2Connect) {
    http2.connect = origH2Connect;
    origH2Connect = null;
  }
  patched = false;
  native = null;
}

function patch() {
  if (patched) return;
  patched = true;

  // Patch tls.connect for HTTP/1.1 traffic
  origTlsConnect = tls.connect;
  tls.connect = function (...args) {
    const socket = origTlsConnect.apply(this, args);
    instrumentTlsSocket(socket);
    return socket;
  };

  // Patch http2.connect for HTTP/2 traffic (AWS SDK v3)
  origH2Connect = http2.connect;
  http2.connect = function (...args) {
    const session = origH2Connect.apply(this, args);
    instrumentH2Session(session, args[0]);
    return session;
  };
}

// --- HTTP/2 interception (AWS SDK v3, modern clients) ---

function instrumentH2Session(session, authority) {
  const origin =
    typeof authority === "string" ? authority : authority.toString();

  // Only instrument sessions to LLM provider hosts
  if (!isLlmHost(origin)) return;

  const origRequest = session.request.bind(session);
  session.request = function (headers, options) {
    const stream = origRequest(headers, options);
    instrumentH2Stream(stream, origin, headers);
    return stream;
  };
}

function isLlmHost(origin) {
  return (
    origin.includes("bedrock-runtime") ||
    origin.includes("openai.com") ||
    origin.includes("anthropic.com")
  );
}

function instrumentH2Stream(stream, origin, headers) {
  const path = headers[":path"] || "/";
  const url = origin.replace(/\/$/, "") + path;

  const reqChunks = [];
  const resChunks = [];
  let reqBodySent = false;

  // Start ARN resolution early, store the promise
  const arnPromise = isArnUrl(url) ? resolveAwsArn(url) : null;

  const origWrite = stream.write.bind(stream);
  const origEnd = stream.end.bind(stream);

  stream.write = function (chunk, encoding, callback) {
    if (chunk)
      reqChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    return origWrite(chunk, encoding, callback);
  };

  stream.end = function (chunk, encoding, callback) {
    if (chunk)
      reqChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));

    const body = Buffer.concat(reqChunks).toString("utf-8");

    if (native && body.trim()) {
      try {
        const result = native.interceptRequest(url, body);
        if (result.allowed === 1) {
          reqBodySent = true;
        }
      } catch (_) {}
    }

    return origEnd(chunk, encoding, callback);
  };

  stream.on("data", (chunk) => {
    if (reqBodySent) {
      resChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
  });

  stream.on("end", async () => {
    if (!reqBodySent || !native) return;

    try {
      let body = Buffer.concat(resChunks);

      const responseHeaders = stream.sentHeaders || {};
      const encoding =
        responseHeaders["content-encoding"] ||
        (stream.headers && stream.headers["content-encoding"]);

      if (encoding === "gzip") body = zlib.gunzipSync(body);
      else if (encoding === "deflate") body = zlib.inflateSync(body);
      else if (encoding === "br") body = zlib.brotliDecompressSync(body);

      let finalUrl = url;
      if (arnPromise) {
        const resolvedModel = await arnPromise;
        if (resolvedModel) {
          finalUrl = url.replace(
            /\/model\/[^/]+\//,
            `/model/regional.${resolvedModel}/`,
          );
        }
      }

      native.interceptResponse(finalUrl, body.toString("utf-8"));
    } catch (_) {}
  });
}

// --- TLS interception for HTTP/1.1 traffic (axios, node-fetch, got) ---

const sendBuffers = new Map();
const recvBuffers = new Map();
const sockUrls = new Map();
const sockReqBody = new Map();
const sockModels = new Map();
const recvMeta = new Map();

let idCounter = 0;
function socketId(socket) {
  if (!socket._zgrcId) socket._zgrcId = ++idCounter;
  return socket._zgrcId;
}

function instrumentTlsSocket(socket) {
  const origWrite = socket.write;
  const origPush = socket.push;

  socket.write = function (data, encoding, callback) {
    const result = origWrite.call(this, data, encoding, callback);
    try {
      handleTlsSend(socket, data);
    } catch (_) {}
    return result;
  };

  socket.push = function (chunk, encoding) {
    if (chunk !== null) {
      try {
        handleTlsRecv(
          socket,
          Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk),
        );
      } catch (_) {}
    }
    return origPush.call(this, chunk, encoding);
  };
}

function handleTlsSend(socket, data) {
  if (!native) return;

  const sid = socketId(socket);
  const raw = Buffer.isBuffer(data) ? data : Buffer.from(data);
  const buf = Buffer.concat([sendBuffers.get(sid) || Buffer.alloc(0), raw]);
  sendBuffers.set(sid, buf);

  if (!buf.includes("\r\n\r\n")) return;
  if (!isHttpRequest(buf)) {
    sendBuffers.delete(sid);
    return;
  }

  const headerEnd = buf.indexOf("\r\n\r\n");
  const headerSection = buf.slice(0, headerEnd).toString("utf-8");
  const bodyBytes = buf.slice(headerEnd + 4);

  const firstLine = headerSection.split("\r\n")[0];
  const parts = firstLine.split(" ");
  const path = parts[1] || "/";
  const body = bodyBytes.toString("utf-8");

  if (!sockUrls.has(sid)) {
    const host = socket.servername || "";
    if (!host) {
      sendBuffers.delete(sid);
      return;
    }
    const fullUrl = `https://${host}${path}`;
    sockUrls.set(sid, fullUrl);

    if (path.includes("arn") && path.includes("/model/")) {
      resolveAwsArn(fullUrl).then((model) => {
        if (model) sockModels.set(sid, model);
      });
    }
  }

  const fullUrl = sockUrls.get(sid);

  if (body.trim()) {
    sendBuffers.delete(sid);
    try {
      const reqResult = native.interceptRequest(fullUrl, body);
      if (reqResult.allowed === 1) {
        sockReqBody.set(sid, true);
      }
    } catch (_) {}
  }
}

function handleTlsRecv(socket, chunk) {
  if (!native) return;

  const sid = socketId(socket);
  if (!sockUrls.has(sid)) return;
  if (!sockReqBody.has(sid)) return;

  const url = sockUrls.get(sid);
  const buf = Buffer.concat([recvBuffers.get(sid) || Buffer.alloc(0), chunk]);
  recvBuffers.set(sid, buf);

  if (!buf.includes("\r\n\r\n")) return;

  const headerEnd = buf.indexOf("\r\n\r\n");
  const headerSection = buf.slice(0, headerEnd).toString("utf-8");
  const bodyBytes = buf.slice(headerEnd + 4);

  if (!recvMeta.has(sid)) {
    const isChunked = /transfer-encoding:\s*chunked/i.test(headerSection);
    const clMatch = headerSection.match(/content-length:\s*(\d+)/i);
    const contentLength = clMatch ? parseInt(clMatch[1]) : -1;
    recvMeta.set(sid, { isChunked, contentLength });
  }

  const { isChunked, contentLength } = recvMeta.get(sid);

  let rawBody;
  if (isChunked) {
    if (!buf.slice(headerEnd + 4).includes("0\r\n\r\n")) return;
    rawBody = decodeChunked(bodyBytes);
  } else if (contentLength >= 0) {
    if (bodyBytes.length < contentLength) return;
    rawBody = bodyBytes.slice(0, contentLength);
  } else {
    return;
  }

  const ceMatch = headerSection.match(/content-encoding:\s*(\S+)/i);
  if (ceMatch) {
    const enc = ceMatch[1].toLowerCase();
    try {
      if (enc === "gzip") rawBody = zlib.gunzipSync(rawBody);
      else if (enc === "deflate") rawBody = zlib.inflateSync(rawBody);
      else if (enc === "br") rawBody = zlib.brotliDecompressSync(rawBody);
    } catch (_) {}
  }

  let finalUrl = url;
  if (sockModels.has(sid)) {
    const model = sockModels.get(sid);
    finalUrl = url.replace(/\/model\/[^/]+\//, `/model/regional.${model}/`);
  }

  try {
    native.interceptResponse(finalUrl, rawBody.toString("utf-8"));
  } catch (_) {}

  recvBuffers.delete(sid);
  recvMeta.delete(sid);
  sockUrls.delete(sid);
  sockReqBody.delete(sid);
  sockModels.delete(sid);
}

function isHttpRequest(buf) {
  const methods = [
    "GET ",
    "POST ",
    "PUT ",
    "DELETE ",
    "PATCH ",
    "HEAD ",
    "OPTIONS ",
  ];
  const start = buf.slice(0, 10).toString("utf-8");
  return methods.some((m) => start.startsWith(m));
}

function decodeChunked(data) {
  const chunks = [];
  let offset = 0;

  while (offset < data.length) {
    const crlfIdx = data.indexOf("\r\n", offset);
    if (crlfIdx === -1) break;
    const sizeStr = data.slice(offset, crlfIdx).toString("utf-8").trim();
    const chunkSize = parseInt(sizeStr, 16);
    if (chunkSize === 0) break;
    const chunkStart = crlfIdx + 2;
    chunks.push(data.slice(chunkStart, chunkStart + chunkSize));
    offset = chunkStart + chunkSize + 2;
  }

  return Buffer.concat(chunks);
}

module.exports = { activate, deactivate };

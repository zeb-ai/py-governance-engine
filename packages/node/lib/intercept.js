/* global setImmediate */
"use strict";

const fs = require("fs");
const tls = require("tls");
const http2 = require("http2");
const zlib = require("zlib");
const { resolveAwsArn } = require("./resolve-arn");

class Util {
  static toBuf(chunk) {
    return Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
  }

  static quotaError(result) {
    const used = Number(result.usedQuota || 0).toFixed(4);
    const remaining = Number(result.remainingQuota || 0).toFixed(4);
    const err = new Error(
      `Quota exceeded. Used: ${used}, Remaining: ${remaining}`,
    );
    err.name = "QuotaExceededError";
    err.usedQuota = result.usedQuota;
    err.remainingQuota = result.remainingQuota;
    return err;
  }

  static decompress(buf, encoding) {
    if (!encoding) return buf;
    try {
      switch (String(encoding).toLowerCase()) {
        case "gzip":
          return zlib.gunzipSync(buf);
        case "deflate":
          return zlib.inflateSync(buf);
        case "br":
          return zlib.brotliDecompressSync(buf);
        default:
          return buf;
      }
    } catch {
      return buf;
    }
  }

  static mapModelUrl(url, model, prefix = "") {
    if (!model) return url;
    return url.replace(/\/model\/[^/]+\//, `/model/${prefix}${model}/`);
  }
}

class FileLogger {
  constructor(level, path) {
    this.level = level;
    this.fd = fs.openSync(path, "a");
  }

  write(levelStr, msg) {
    const ts = new Date().toISOString().replace("T", " ").replace("Z", "");
    fs.writeSync(this.fd, `[${ts}] [JS] [${levelStr}] ${msg}\n`);
  }

  debug(msg) {
    if (this.level <= 0) this.write("DEBUG", msg);
  }
  info(msg) {
    if (this.level <= 1) this.write("INFO", msg);
  }
  warn(msg) {
    if (this.level <= 2) this.write("WARN", msg);
  }
  error(msg) {
    if (this.level <= 3) this.write("ERROR", msg);
  }

  close() {
    try {
      fs.closeSync(this.fd);
    } catch {
      /* ignore */
    }
  }
}

let jsLogger = null;

function jlog() {
  return jsLogger;
}

class ArnResolver {
  static ARN_PREFIX = "arn:aws:bedrock:";
  // arn:aws:bedrock:<region>:<account?>:<resourceType>/<resourceId...>
  static ARN_RE = /^arn:aws:bedrock:([a-z0-9-]+):\d*:([a-z-]+)\/(.+)$/i;

  constructor(bridge) {
    this.bridge = bridge; // for logErr only
    this.cache = new Map(); // arn -> Promise<string|null>
    this.clients = new Map(); // region -> BedrockClient
    this._sdk = undefined; // lazily resolved control-plane SDK (or null)
    this._warnedNoSdk = false;
  }

  static modelSegment(url) {
    const m = String(url).match(/\/model\/([^/]+)\//);
    if (!m) return null;
    try {
      return decodeURIComponent(m[1]);
    } catch {
      return m[1];
    }
  }

  looksLikeArn(url) {
    const seg = ArnResolver.modelSegment(url);
    return !!seg && seg.startsWith(ArnResolver.ARN_PREFIX);
  }

  resolveModel(url) {
    const arn = ArnResolver.modelSegment(url);
    if (!arn || !arn.startsWith(ArnResolver.ARN_PREFIX))
      return Promise.resolve(null);

    if (!this.cache.has(arn)) {
      const p = this._resolve(url, arn).then(
        (model) => {
          if (!model) this.cache.delete(arn);
          return model;
        },
        (err) => {
          this.bridge.logErr("arn.resolve", err);
          this.cache.delete(arn);
          return null;
        },
      );
      this.cache.set(arn, p);
    }
    return this.cache.get(arn);
  }

  async _resolve(url, arn) {
    jlog()?.debug(`arn.resolve arn=${arn}`);
    try {
      const fromModule = this._usable(await resolveAwsArn(url), arn);
      if (fromModule) {
        jlog()?.info(`arn.resolve resolved=${fromModule}`);
        return fromModule;
      }
    } catch (err) {
      this.bridge.logErr("arn.resolveAwsArn", err);
      jlog()?.error(`arn.resolveAwsArn ${err.message}`);
    }
    return this._resolveFromArn(arn);
  }

  _usable(model, arn) {
    if (!model || typeof model !== "string") return null;
    if (model === arn || model.startsWith(ArnResolver.ARN_PREFIX)) return null;
    return model;
  }

  async _resolveFromArn(arn) {
    const m = arn.match(ArnResolver.ARN_RE);
    if (!m) return null;
    const region = m[1];
    const type = m[2];
    const id = m[3];

    if (type === "foundation-model") return id;
    if (type === "inference-profile")
      return id.replace(/^(us|eu|apac|us-gov)\./i, "");
    if (type === "application-inference-profile")
      return this._lookupProfile(arn, region);
    return null;
  }

  async _lookupProfile(arn, region) {
    const sdk = this._loadSdk();
    if (!sdk) return null;

    const out = await this._clientFor(region, sdk).send(
      new sdk.GetInferenceProfileCommand({ inferenceProfileIdentifier: arn }),
    );
    const modelArn =
      out && out.models && out.models[0] && out.models[0].modelArn;
    if (!modelArn) return null;

    const fm = modelArn.match(/foundation-model\/(.+)$/);
    return fm ? fm[1] : modelArn;
  }

  _loadSdk() {
    if (this._sdk !== undefined) return this._sdk;
    try {
      this._sdk = require("@aws-sdk/client-bedrock");
    } catch {
      this._sdk = null;
      if (!this._warnedNoSdk) {
        this._warnedNoSdk = true;
        console.error(
          "[z-grc] cannot resolve application-inference-profile ARNs: install " +
            "@aws-sdk/client-bedrock and grant bedrock:GetInferenceProfile",
        );
      }
    }
    return this._sdk;
  }

  _clientFor(region, sdk) {
    if (!this.clients.has(region))
      this.clients.set(region, new sdk.BedrockClient({ region }));
    return this.clients.get(region);
  }
}

class EventStreamParser {
  static CONTENT_TYPE = "application/vnd.amazon.eventstream";

  static FIXED_HEADER_SIZES = {
    0: 0,
    1: 0,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    8: 8,
    9: 16,
  };
  static TYPE_STRING = 7;
  static TYPE_BYTES = 6;

  static parseMetadata(buf) {
    let offset = 0;
    let metadataPayload = null;

    while (offset + 12 <= buf.length) {
      const totalLen = buf.readUInt32BE(offset);
      if (totalLen < 16 || offset + totalLen > buf.length) break;

      const headersLen = buf.readUInt32BE(offset + 4);
      const headersStart = offset + 12;
      const headersEnd = headersStart + headersLen;
      const payloadStart = headersEnd;
      const payloadEnd = offset + totalLen - 4; // exclude trailing message CRC

      if (this._readEventType(buf, headersStart, headersEnd) === "metadata") {
        metadataPayload = buf.slice(payloadStart, payloadEnd).toString("utf-8");
      }

      offset += totalLen;
    }

    return metadataPayload;
  }

  static _readEventType(buf, start, end) {
    let pos = start;

    while (pos < end) {
      const nameLen = buf.readUInt8(pos);
      pos += 1;
      if (pos + nameLen > end) break;

      const name = buf.slice(pos, pos + nameLen).toString("utf-8");
      pos += nameLen;

      const type = buf.readUInt8(pos);
      pos += 1;

      if (type === this.TYPE_STRING) {
        const len = buf.readUInt16BE(pos);
        pos += 2;
        if (pos + len > end) break;
        const value = buf.slice(pos, pos + len).toString("utf-8");
        pos += len;
        if (name === ":event-type") return value;
      } else if (type === this.TYPE_BYTES) {
        const len = buf.readUInt16BE(pos);
        pos += 2 + len;
      } else if (type in this.FIXED_HEADER_SIZES) {
        pos += this.FIXED_HEADER_SIZES[type];
      } else {
        break; // unknown wire type
      }
    }

    return null;
  }
}

class ChunkedDecoder {
  static decode(data) {
    const chunks = [];
    let offset = 0;

    while (offset < data.length) {
      const crlf = data.indexOf("\r\n", offset);
      if (crlf === -1) break;

      const size = parseInt(
        data.slice(offset, crlf).toString("utf-8").trim(),
        16,
      );
      if (!size) break; // final chunk

      const start = crlf + 2;
      chunks.push(data.slice(start, start + size));
      offset = start + size + 2; // skip trailing CRLF
    }

    return Buffer.concat(chunks);
  }
}

class InterceptorConfig {
  constructor() {
    /** Block requests when native reports quota exhausted (allowed === 0). */
    this.enforceQuota = true;
    /** A request is governed if its host contains any of these substrings. */
    this.llmHosts = ["bedrock-runtime", "openai.com", "anthropic.com"];
    /** Log swallowed internal errors to stderr. */
    this.debug = false;
    /**
     * Prefix prepended to a resolved model id when rewriting an ARN url.
     * Default "" sends the bare model id (matches Bedrock cost-table keys).
     * Set to e.g. "regional." only if your native cost table is keyed that way.
     */
    this.arnModelPrefix = "";
  }

  isLlmHost(host) {
    if (!host) return false;
    return this.llmHosts.some((pattern) => host.includes(pattern));
  }
}

class NativeBridge {
  static ALLOW = Object.freeze({ allowed: 1, usedQuota: 0, remainingQuota: 0 });

  constructor(config) {
    this.config = config;
    this.native = null;
  }

  set(native) {
    this.native = native || null;
  }

  clear() {
    this.native = null;
  }

  get active() {
    return this.native != null;
  }

  logErr(where, err) {
    if (this.config.debug) console.error(`[z-grc] ${where}:`, err);
  }

  /** @returns {{allowed:number, usedQuota:number, remainingQuota:number}} */
  interceptRequest(url, body) {
    if (!this.native) return NativeBridge.ALLOW;
    try {
      return this.native.interceptRequest(url, body) || NativeBridge.ALLOW;
    } catch (err) {
      this.logErr("interceptRequest", err);
      return NativeBridge.ALLOW; // fail open
    }
  }

  interceptResponse(url, body) {
    if (!this.native) return;
    try {
      this.native.interceptResponse(url, body);
    } catch (err) {
      this.logErr("interceptResponse", err);
    }
  }
}

// Http2StreamTap — instruments ONE HTTP/2 request/response stream

class Http2StreamTap {
  /**
   * @param {import("http2").ClientHttp2Stream} stream
   * @param {string} origin   e.g. "https://bedrock-runtime.us-east-1.amazonaws.com"
   * @param {object} headers  outbound request headers (incl. :path, :method)
   * @param {{config: InterceptorConfig, bridge: NativeBridge, resolver: ArnResolver}} ctx
   */
  constructor(stream, origin, headers, ctx) {
    this.stream = stream;
    this.ctx = ctx;

    const path = headers[":path"] || "/";
    this.url = origin.replace(/\/$/, "") + path;

    this.reqChunks = [];
    this.resChunks = [];
    this.allowed = false; // true once the request is mirrored & permitted
    this.isEventStream = false;
    this.resHeaders = null;
    // Start ARN resolution early; awaited when the response finalizes.
    this.modelPromise = ctx.resolver.looksLikeArn(this.url)
      ? ctx.resolver.resolveModel(this.url)
      : null;
    this.finalized = false;
  }

  attach() {
    this._tapRequest();
    this._tapResponse();
  }

  // --- request: capture body, mirror to native, optionally enforce quota ---

  _tapRequest() {
    const origWrite = this.stream.write.bind(this.stream);
    const origEnd = this.stream.end.bind(this.stream);

    this.stream.write = (chunk, encoding, callback) => {
      if (chunk) this.reqChunks.push(Util.toBuf(chunk));
      return origWrite(chunk, encoding, callback);
    };

    this.stream.end = (chunk, encoding, callback) => {
      // Normalize the overloaded end(...) signatures.
      if (typeof chunk === "function") {
        callback = chunk;
        chunk = undefined;
        encoding = undefined;
      } else if (typeof encoding === "function") {
        callback = encoding;
        encoding = undefined;
      }
      if (chunk) this.reqChunks.push(Util.toBuf(chunk));

      const body = Buffer.concat(this.reqChunks).toString("utf-8");
      if (body.trim()) {
        jlog()?.debug(`h2.request url=${this.url} body_len=${body.length}`);
        const result = this.ctx.bridge.interceptRequest(this.url, body);
        if (this.ctx.config.enforceQuota && result && result.allowed === 0) {
          jlog()?.warn(`h2.request quota_exceeded url=${this.url}`);
          this._reject(result); // block: do not send
          return this.stream;
        }
        this.allowed = true;
        jlog()?.info(`h2.request allowed url=${this.url}`);
      }

      return origEnd(chunk, encoding, callback);
    };
  }

  // --- response: transparent observation via push(), finalize once on EOF ---

  _tapResponse() {
    // Listening to 'response' does not affect data flow.
    this.stream.on("response", (resHeaders) => {
      this.resHeaders = resHeaders;
      const ct = resHeaders["content-type"] || "";
      if (ct.includes(EventStreamParser.CONTENT_TYPE))
        this.isEventStream = true;
    });

    // push() feeds incoming data into the readable side. Overriding it lets us
    // copy every chunk while forwarding it unchanged, so the consumer keeps
    // working in any read mode (data/pipe/async-iterator) and backpressure is
    // preserved (we return the original push()'s boolean).
    const origPush = this.stream.push.bind(this.stream);
    this.stream.push = (chunk, encoding) => {
      if (chunk === null) {
        this._finalizeResponse(); // EOF
      } else if (this.allowed) {
        this.resChunks.push(Util.toBuf(chunk));
      }
      return origPush(chunk, encoding);
    };
  }

  _finalizeResponse() {
    if (this.finalized || !this.allowed || this.resChunks.length === 0) return;
    this.finalized = true;

    // Defer so we never delay the consumer's own 'end' event.
    setImmediate(async () => {
      try {
        const encoding = this.resHeaders && this.resHeaders["content-encoding"];
        const body = Util.decompress(Buffer.concat(this.resChunks), encoding);
        const url = await this._resolveUrl();

        if (this.isEventStream) {
          const metadata = EventStreamParser.parseMetadata(body);
          jlog()?.debug(
            `h2.response event_stream url=${url} has_metadata=${!!metadata}`,
          );
          if (metadata) this.ctx.bridge.interceptResponse(url, metadata);
        } else {
          jlog()?.debug(`h2.response url=${url} body_len=${body.length}`);
          this.ctx.bridge.interceptResponse(url, body.toString("utf-8"));
        }
      } catch (err) {
        this.ctx.bridge.logErr("h2.finalizeResponse", err);
        jlog()?.error(`h2.finalizeResponse ${err.message}`);
      }
    });
  }

  async _resolveUrl() {
    if (!this.modelPromise) return this.url;
    try {
      const model = await this.modelPromise;
      return Util.mapModelUrl(this.url, model, this.ctx.config.arnModelPrefix);
    } catch {
      return this.url;
    }
  }

  _reject(result) {
    const err = Util.quotaError(result);
    // Destroy asynchronously to avoid corrupting Node's internal stream state.
    setImmediate(() => {
      if (this.stream.destroyed) return;
      this.stream.emit("error", err);
      this.stream.destroy(err);
    });
  }
}

// Http1SocketTap — instruments ONE TLS socket carrying HTTP/1.1 traffic

class Http1SocketTap {
  static METHODS = [
    "GET ",
    "POST ",
    "PUT ",
    "DELETE ",
    "PATCH ",
    "HEAD ",
    "OPTIONS ",
  ];

  /**
   * @param {import("tls").TLSSocket} socket
   * @param {{config: InterceptorConfig, bridge: NativeBridge, resolver: ArnResolver}} ctx
   */
  constructor(socket, ctx) {
    this.socket = socket;
    this.ctx = ctx;
    this._resetRequest();
  }

  attach() {
    // write() -> outgoing (request) plaintext; push() -> incoming (response).
    // Originals are always forwarded, so the socket behaves exactly as before.
    const origWrite = this.socket.write.bind(this.socket);
    const origPush = this.socket.push.bind(this.socket);

    this.socket.write = (data, encoding, callback) => {
      const result = origWrite(data, encoding, callback);
      try {
        this._handleSend(data);
      } catch (err) {
        this.ctx.bridge.logErr("h1.send", err);
      }
      return result;
    };

    this.socket.push = (chunk, encoding) => {
      if (chunk !== null) {
        try {
          this._handleRecv(Util.toBuf(chunk));
        } catch (err) {
          this.ctx.bridge.logErr("h1.recv", err);
        }
      }
      return origPush(chunk, encoding);
    };
  }

  _resetRequest() {
    this.sendBuf = Buffer.alloc(0);
    this.recvBuf = Buffer.alloc(0);
    this.url = null;
    this.allowed = false;
    this.recvMeta = null;
    this.model = null;
  }

  _isHttpRequest(buf) {
    const start = buf.slice(0, 10).toString("utf-8");
    return Http1SocketTap.METHODS.some((m) => start.startsWith(m));
  }

  // --- request side ---

  _handleSend(data) {
    const { bridge, config, resolver } = this.ctx;
    if (!bridge.active) return;

    this.sendBuf = Buffer.concat([this.sendBuf, Util.toBuf(data)]);

    const headerEnd = this.sendBuf.indexOf("\r\n\r\n");
    if (headerEnd === -1) return; // headers incomplete

    if (!this._isHttpRequest(this.sendBuf)) {
      this.sendBuf = Buffer.alloc(0);
      return;
    }

    const headerSection = this.sendBuf.slice(0, headerEnd).toString("utf-8");
    const bodyBytes = this.sendBuf.slice(headerEnd + 4);

    if (!this.url) {
      const host = this.socket.servername || "";
      if (!host) {
        this.sendBuf = Buffer.alloc(0);
        return;
      }
      const path = headerSection.split("\r\n")[0].split(" ")[1] || "/";
      this.url = `https://${host}${path}`;

      if (resolver.looksLikeArn(this.url)) {
        resolver
          .resolveModel(this.url)
          .then((model) => {
            if (model) this.model = model;
          })
          .catch(() => {});
      }
    }

    const body = bodyBytes.toString("utf-8");
    if (!body.trim()) return; // wait for the body

    this.sendBuf = Buffer.alloc(0);

    jlog()?.debug(`h1.request url=${this.url} body_len=${body.length}`);
    const result = bridge.interceptRequest(this.url, body);
    if (config.enforceQuota && result && result.allowed === 0) {
      jlog()?.warn(`h1.request quota_exceeded url=${this.url}`);
      this._reject(result);
      return;
    }
    this.allowed = true;
    jlog()?.info(`h1.request allowed url=${this.url}`);
  }

  // --- response side ---

  _handleRecv(chunk) {
    const { bridge, config } = this.ctx;
    if (!bridge.active) return;
    if (!this.url || !this.allowed) return;

    this.recvBuf = Buffer.concat([this.recvBuf, chunk]);

    const headerEnd = this.recvBuf.indexOf("\r\n\r\n");
    if (headerEnd === -1) return;

    const headerSection = this.recvBuf.slice(0, headerEnd).toString("utf-8");
    const bodyBytes = this.recvBuf.slice(headerEnd + 4);

    if (!this.recvMeta) {
      const cl = headerSection.match(/content-length:\s*(\d+)/i);
      const ce = headerSection.match(/content-encoding:\s*(\S+)/i);
      this.recvMeta = {
        isChunked: /transfer-encoding:\s*chunked/i.test(headerSection),
        contentLength: cl ? parseInt(cl[1], 10) : -1,
        encoding: ce ? ce[1].toLowerCase() : null,
      };
    }

    const { isChunked, contentLength, encoding } = this.recvMeta;

    let rawBody;
    if (isChunked) {
      if (!bodyBytes.includes("0\r\n\r\n")) return; // wait for terminator
      rawBody = ChunkedDecoder.decode(bodyBytes);
    } else if (contentLength >= 0) {
      if (bodyBytes.length < contentLength) return; // wait for full body
      rawBody = bodyBytes.slice(0, contentLength);
    } else {
      return; // no length info; cannot safely delimit
    }

    rawBody = Util.decompress(rawBody, encoding);
    const url = Util.mapModelUrl(this.url, this.model, config.arnModelPrefix);

    jlog()?.debug(`h1.response url=${url} body_len=${rawBody.length}`);
    bridge.interceptResponse(url, rawBody.toString("utf-8"));
    this._resetRequest(); // ready for keep-alive reuse
  }

  _reject(result) {
    const err = Util.quotaError(result);
    setImmediate(() => {
      if (this.socket.destroyed) return;
      this.socket.emit("error", err);
      this.socket.destroy(err);
    });
  }
}

// Interceptor — orchestrator: patches tls.connect + http2.connect

class Interceptor {
  constructor() {
    this.config = new InterceptorConfig();
    this.bridge = new NativeBridge(this.config);
    this.resolver = new ArnResolver(this.bridge);
    this._originals = null; // { tlsConnect, h2Connect }
  }

  /** Context handed to each per-connection tap. */
  get _ctx() {
    return {
      config: this.config,
      bridge: this.bridge,
      resolver: this.resolver,
    };
  }

  /**
   * Start intercepting. Safe to call again to (re)bind the native module
   * without re-patching.
   */
  activate(nativeModule) {
    this.bridge.set(nativeModule);
    if (this._originals) return this;

    this._originals = { tlsConnect: tls.connect, h2Connect: http2.connect };
    jlog()?.info("interceptor activated: patching tls.connect + http2.connect");

    tls.connect = (...args) => {
      const socket = this._originals.tlsConnect(...args);
      try {
        new Http1SocketTap(socket, this._ctx).attach();
      } catch (err) {
        this.bridge.logErr("patch.tls", err);
        jlog()?.error(`patch.tls ${err.message}`);
      }
      return socket;
    };

    http2.connect = (...args) => {
      const session = this._originals.h2Connect(...args);
      jlog()?.debug(`h2.connect origin=${args[0]}`);
      try {
        this._instrumentSession(session, args[0]);
      } catch (err) {
        this.bridge.logErr("patch.http2", err);
        jlog()?.error(`patch.http2 ${err.message}`);
      }
      return session;
    };

    return this;
  }

  /** Stop intercepting and restore the original tls/http2 entry points. */
  deactivate() {
    if (this._originals) {
      tls.connect = this._originals.tlsConnect;
      http2.connect = this._originals.h2Connect;
      this._originals = null;
    }
    jlog()?.info("interceptor deactivated");
    this.bridge.clear();
    return this;
  }

  _instrumentSession(session, authority) {
    const origin =
      typeof authority === "string" ? authority : String(authority || "");
    if (!this.config.isLlmHost(origin)) return;

    const origRequest = session.request.bind(session);
    session.request = (headers, options) => {
      const stream = origRequest(headers, options);
      try {
        new Http2StreamTap(stream, origin, headers, this._ctx).attach();
      } catch (err) {
        this.bridge.logErr("h2.instrumentStream", err);
      }
      return stream;
    };
  }
}

const defaultInterceptor = new Interceptor();

module.exports = {
  activate: (native) => defaultInterceptor.activate(native),
  deactivate: () => defaultInterceptor.deactivate(),
  config: defaultInterceptor.config,
  setLogger: (logger) => {
    jsLogger = logger;
  },
  FileLogger,
};

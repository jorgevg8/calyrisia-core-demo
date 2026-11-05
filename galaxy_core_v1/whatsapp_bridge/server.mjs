import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState
} from '@whiskeysockets/baileys';
import QRCode from 'qrcode';
import pino from 'pino';

const BRIDGE_PORT = Number(process.env.WA_BRIDGE_PORT || 3001);
const FASTAPI_BASE = process.env.WA_FASTAPI_BASE || `http://127.0.0.1:${process.env.PORT || 8000}`;
const BRIDGE_SECRET = process.env.WA_BRIDGE_SECRET || 'calyrisia-internal-wa-bridge-secret';
const AUTH_BASE_DIR = path.join(os.tmpdir(), 'calyrisia_wa_auth');

const logger = pino({ level: 'silent' });
const sessions = new Map(); // businessId -> { sock, status, starting, syncTimer }
const processedMsgIds = new Set();

async function callFastApi(endpoint, method = 'GET', body = null) {
  const res = await fetch(`${FASTAPI_BASE}${endpoint}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-WA-Bridge-Secret': BRIDGE_SECRET
    },
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

async function restoreAuthFilesFromSupabase(businessId, dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
  try {
    const { ok, data } = await callFastApi(`/api/v1/internal/whatsapp/auth-files/${encodeURIComponent(businessId)}`);
    if (!ok || !data || !data.files) return;
    for (const [fileName, content] of Object.entries(data.files)) {
      const safeName = path.basename(fileName);
      await fs.writeFile(path.join(dirPath, safeName), String(content), 'utf-8');
    }
  } catch (err) {
    // Primera sesión o FastAPI aún iniciando
  }
}

async function backupAuthFilesToSupabase(businessId, dirPath) {
  try {
    const entries = await fs.readdir(dirPath);
    const files = {};
    for (const name of entries) {
      if (!name.endsWith('.json')) continue;
      const content = await fs.readFile(path.join(dirPath, name), 'utf-8');
      files[name] = content;
    }
    if (Object.keys(files).length > 0) {
      await callFastApi(`/api/v1/internal/whatsapp/auth-files/${encodeURIComponent(businessId)}`, 'POST', { files });
    }
  } catch (err) {
    // Ignore transient fs errors
  }
}

function scheduleAuthBackup(businessId, dirPath) {
  const entry = sessions.get(businessId);
  if (!entry) return;
  if (entry.syncTimer) clearTimeout(entry.syncTimer);
  entry.syncTimer = setTimeout(() => {
    backupAuthFilesToSupabase(businessId, dirPath);
  }, 1200);
}

function extractMessageText(msg) {
  const m = msg?.message;
  if (!m) return '';
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.documentMessage?.caption ||
    m.buttonsResponseMessage?.selectedDisplayText ||
    m.listResponseMessage?.title ||
    ''
  ).trim();
}

async function startBusinessSession(businessId, pairingPhone = '') {
  const existing = sessions.get(businessId);
  if (existing?.starting) {
    return { status: 'starting' };
  }
  if (existing?.sock) {
    try {
      existing.sock.ev.removeAllListeners();
      existing.sock.ws?.close();
    } catch (_) {}
  }

  const dirPath = path.join(AUTH_BASE_DIR, businessId);
  sessions.set(businessId, { sock: null, status: 'starting', starting: true, syncTimer: null });

  await restoreAuthFilesFromSupabase(businessId, dirPath);
  const { state, saveCreds } = await useMultiFileAuthState(dirPath);
  let version = [2, 3000, 1015901307];
  try {
    const latest = await fetchLatestBaileysVersion();
    if (latest?.version) version = latest.version;
  } catch (_) {}

  const sock = makeWASocket({
    version,
    logger,
    printQRInTerminal: false,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger)
    },
    browser: ['CALYRISIA AI', 'Chrome', '120.0.0'],
    markOnlineOnConnect: false,
    generateHighQualityLinkPreview: false,
    syncFullHistory: false
  });

  sessions.set(businessId, { sock, status: 'starting', starting: false, syncTimer: null });

  if (pairingPhone && !sock.authState.creds.registered) {
    const cleanDigits = String(pairingPhone).replace(/\D/g, '');
    if (cleanDigits.length >= 8) {
      setTimeout(async () => {
        try {
          const code = await sock.requestPairingCode(cleanDigits);
          await callFastApi('/api/v1/internal/whatsapp/status', 'POST', {
            business_id: businessId,
            status: 'qr_ready',
            pairing_code: code
          });
        } catch (_) {}
      }, 2200);
    }
  }

  sock.ev.on('creds.update', async () => {
    await saveCreds();
    scheduleAuthBackup(businessId, dirPath);
  });

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      try {
        const qrDataUrl = await QRCode.toDataURL(qr, { margin: 2, width: 300 });
        const cur = sessions.get(businessId);
        if (cur) cur.status = 'qr_ready';
        await callFastApi('/api/v1/internal/whatsapp/status', 'POST', {
          business_id: businessId,
          status: 'qr_ready',
          qr_code_data_url: qrDataUrl
        });
      } catch (_) {}
    }

    if (connection === 'open') {
      const cur = sessions.get(businessId);
      if (cur) cur.status = 'connected';
      const rawId = String(sock.user?.id || '');
      const phone = rawId.split(':')[0].split('@')[0];
      const name = String(sock.user?.name || 'WhatsApp Negocio');
      await backupAuthFilesToSupabase(businessId, dirPath);
      await callFastApi('/api/v1/internal/whatsapp/status', 'POST', {
        business_id: businessId,
        status: 'connected',
        phone_number: phone ? `+${phone}` : '',
        display_name: name,
        qr_code_data_url: null,
        pairing_code: null,
        last_error: null
      });
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = statusCode === DisconnectReason.loggedOut;
      if (loggedOut) {
        sessions.delete(businessId);
        try {
          await fs.rm(dirPath, { recursive: true, force: true });
        } catch (_) {}
        await callFastApi('/api/v1/internal/whatsapp/status', 'POST', {
          business_id: businessId,
          status: 'disconnected',
          qr_code_data_url: null,
          pairing_code: null,
          clear_auth: true,
          last_error: 'Sesión cerrada desde el teléfono.'
        });
      } else {
        setTimeout(() => {
          startBusinessSession(businessId).catch(() => {});
        }, 4000);
      }
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify' || !Array.isArray(messages)) return;
    for (const msg of messages) {
      try {
        if (!msg?.message || msg.key?.fromMe) continue;
        const remoteJid = String(msg.key?.remoteJid || '');
        if (
          !remoteJid ||
          remoteJid === 'status@broadcast' ||
          remoteJid.endsWith('@g.us') ||
          remoteJid.endsWith('@newsletter')
        ) {
          continue;
        }
        const msgId = String(msg.key?.id || '');
        if (msgId && processedMsgIds.has(`${businessId}:${msgId}`)) continue;
        if (msgId) {
          processedMsgIds.add(`${businessId}:${msgId}`);
          if (processedMsgIds.size > 2000) {
            const first = processedMsgIds.values().next().value;
            processedMsgIds.delete(first);
          }
        }

        const text = extractMessageText(msg);
        if (!text) continue;

        const senderPhone = remoteJid.split('@')[0].split(':')[0];
        const senderName = String(msg.pushName || 'Cliente WhatsApp');

        // Pausa natural humana + estado "Escribiendo..." para proteger el número
        try {
          await sock.sendPresenceUpdate('composing', remoteJid);
        } catch (_) {}
        await new Promise((r) => setTimeout(r, 1800));

        const { ok, data } = await callFastApi('/api/v1/internal/whatsapp/incoming', 'POST', {
          business_id: businessId,
          sender_phone: senderPhone,
          sender_name: senderName,
          message_text: text,
          message_id: msgId
        });

        try {
          await sock.sendPresenceUpdate('paused', remoteJid);
        } catch (_) {}

        if (ok && data?.reply_text) {
          await sock.sendMessage(remoteJid, { text: String(data.reply_text) });
        }
      } catch (err) {
        // Never crash the socket loop on a single message
      }
    }
  });

  return { status: 'starting' };
}

async function stopBusinessSession(businessId) {
  const entry = sessions.get(businessId);
  if (entry?.sock) {
    try {
      await entry.sock.logout();
    } catch (_) {}
    try {
      entry.sock.ev.removeAllListeners();
      entry.sock.ws?.close();
    } catch (_) {}
  }
  sessions.delete(businessId);
  const dirPath = path.join(AUTH_BASE_DIR, businessId);
  try {
    await fs.rm(dirPath, { recursive: true, force: true });
  } catch (_) {}
}

async function sendTextMessage(businessId, toPhone, text) {
  const entry = sessions.get(businessId);
  if (!entry?.sock || entry.status !== 'connected') {
    throw new Error('La sesión de WhatsApp del negocio no está conectada.');
  }
  const cleanDigits = String(toPhone || '').replace(/\D/g, '');
  if (cleanDigits.length < 7) {
    throw new Error('Número de WhatsApp inválido.');
  }
  const jid = `${cleanDigits}@s.whatsapp.net`;
  await entry.sock.sendMessage(jid, { text: String(text || '') });
  return { sent: true };
}

const server = http.createServer(async (req, res) => {
  const sendJson = (code, payload) => {
    res.writeHead(code, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(payload));
  };

  if (req.headers['x-wa-bridge-secret'] !== BRIDGE_SECRET) {
    return sendJson(401, { ok: false, error: 'unauthorized' });
  }

  const url = new URL(req.url || '/', `http://127.0.0.1:${BRIDGE_PORT}`);
  if (req.method === 'GET' && url.pathname === '/health') {
    const active = [];
    for (const [bid, info] of sessions.entries()) {
      active.push({ business_id: bid, status: info.status });
    }
    return sendJson(200, { ok: true, sessions: active });
  }

  let bodyStr = '';
  for await (const chunk of req) bodyStr += chunk;
  let body = {};
  try {
    body = bodyStr ? JSON.parse(bodyStr) : {};
  } catch (_) {}

  try {
    if (req.method === 'POST' && url.pathname === '/session/start') {
      const businessId = String(body.business_id || '').trim();
      if (!businessId) return sendJson(400, { ok: false, error: 'business_id required' });
      const result = await startBusinessSession(businessId, String(body.pairing_phone || ''));
      return sendJson(200, { ok: true, ...result });
    }

    if (req.method === 'POST' && url.pathname === '/session/logout') {
      const businessId = String(body.business_id || '').trim();
      if (!businessId) return sendJson(400, { ok: false, error: 'business_id required' });
      await stopBusinessSession(businessId);
      return sendJson(200, { ok: true, status: 'disconnected' });
    }

    if (req.method === 'POST' && url.pathname === '/session/send') {
      const businessId = String(body.business_id || '').trim();
      const toPhone = String(body.to_phone || '').trim();
      const text = String(body.text || '').trim();
      const result = await sendTextMessage(businessId, toPhone, text);
      return sendJson(200, { ok: true, ...result });
    }

    return sendJson(404, { ok: false, error: 'not_found' });
  } catch (err) {
    return sendJson(500, { ok: false, error: String(err?.message || err) });
  }
});

server.listen(BRIDGE_PORT, '127.0.0.1', () => {
  console.log(`[CALYRISIA][WA-BRIDGE] Escuchando en 127.0.0.1:${BRIDGE_PORT}`);
});

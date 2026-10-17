const urlParams = new URLSearchParams(window.location.search);
// The tenant comes from this storefront URL. Do not inherit another store from localStorage.
let targetBusinessId = urlParams.get("business_id");

const state = {
  businessId: targetBusinessId,
  bizName: "Calyrisia Asesor",
  bizType: "Comercio",
  customerId: null,
  conversationId: null,
  ready: false,
};

const $ = (id) => document.getElementById(id);
let cardCounter = 0;

function updateHeaderUI() {
  const bizNameEl = $("business-name");
  if (bizNameEl) bizNameEl.textContent = state.bizName;
  const typeBadge = $("business-type-badge");
  if (typeBadge) typeBadge.textContent = state.bizType ? state.bizType.toUpperCase() : "ASESOR IA";
  const tenantPill = $("tenant-pill");
  if (tenantPill) {
    if (state.businessId) {
      tenantPill.textContent = `ID: ${state.businessId.slice(0, 8)}...`;
      tenantPill.title = `Tenant activo: ${state.businessId}`;
    } else {
      tenantPill.textContent = "Sin negocio configurado";
    }
  }
  document.title = `${state.bizName} - Asesor IA`;
}

function switchTenant() {
  const current = state.businessId || "";
  const input = prompt("Ingresa el ID del negocio que debe atender este Webchat:", current);
  if (input !== null) {
    const clean = input.trim();
    if (clean) {
      localStorage.setItem("calyrisia_current_business_id", clean);
      window.location.href = `/webchat?business_id=${encodeURIComponent(clean)}`;
    } else {
      alert("Webchat necesita el identificador del negocio. No existe un negocio predeterminado.");
    }
  }
}

function addMessage(role, text) {
  const messagesEl = $("messages");
  if (!messagesEl) return;

  // 1. Extraer si viene etiqueta de botón de pago con items
  let paymentAmount = null;
  let orderItems = [];
  const match = (text || "").match(/\[BOTON_PAGO:\s*([\d\.]+)(?:\|ITEMS:\s*(\[.*?\]))?\]/i);
  if (match) {
    paymentAmount = parseFloat(match[1]);
    if (match[2]) {
      try {
        orderItems = JSON.parse(match[2]);
      } catch (e) {
        console.warn("Error parsing items:", e);
      }
    }
  }

  // 2. Limpiar texto de etiquetas y asteriscos
  let cleanText = (text || "")
    .replace(/\[BOTON_PAGO:[^\]]+\]/gi, "")
    .replace(/\*\*/g, "")
    .replace(/\*/g, "")
    .trim();

  if (cleanText) {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    div.textContent = cleanText;
    messagesEl.appendChild(div);
  }

  // 3. Si hay monto a pagar y el mensaje viene del bot, adjuntar la tarjeta de pago interactiva
  if (paymentAmount && role === "bot") {
    renderPaymentCard(paymentAmount, orderItems);
  }

  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function renderPaymentCard(amount, items = []) {
  cardCounter++;
  const cardId = `pay-card-${cardCounter}`;
  const messagesEl = $("messages");
  if (!messagesEl) return;

  const card = document.createElement("div");
  card.className = "payment-card";
  card.id = cardId;
  card.dataset.items = JSON.stringify(items || []);
  card.innerHTML = `
    <div class="pay-card-header"><span class="pay-badge">INSTRUCCIONES DE PAGO</span><span class="pay-amount">$${amount.toFixed(2)} USD</span></div>
    <div class="pay-title">Métodos de cobro de este negocio</div>
    <div id="pay-instructions-${cardId}" class="pay-info">Consultando las instrucciones configuradas por el comercio…</div>
  `;
  messagesEl.appendChild(card);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  const info = $(`pay-instructions-${cardId}`);
  try {
    if (!state.businessId) throw new Error("No se identificó el negocio.");
    const res = await fetch(`/api/v1/webchat/payment-instructions?business_id=${encodeURIComponent(state.businessId)}`);
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.detail || "No se pudieron cargar las instrucciones de pago.");
    const methods = Array.isArray(data.methods) ? data.methods : [];
    if (!methods.length) {
      info.innerHTML = '<p>El negocio todavía no ha configurado métodos de cobro. Por seguridad, no realices transferencias. Contacta al comercio para recibir instrucciones oficiales.</p>';
      return;
    }
    const methodsHtml = methods.map(m => `<div class="pay-info-row" style="display:block;padding:5px 0;"><strong>${escapeHtmlText(m.label)}</strong><p style="white-space:pre-wrap;margin-top:5px;">${escapeHtmlText(m.instructions)}</p></div>`).join('<hr style="border:0;border-top:1px solid #e2e8f0;margin:7px 0;">');
    const methodOptions = methods.map(m => `<option value="${escapeHtmlText(m.code)}">${escapeHtmlText(m.label)}</option>`).join('');
    info.innerHTML = `${methodsHtml}<label style="display:block;margin-top:10px;font-size:.8rem;">Método utilizado<select id="payment-method-${cardId}" style="display:block;width:100%;margin-top:6px;border:1px solid #cbd5e1;border-radius:9px;padding:9px;font:inherit;">${methodOptions}</select></label><label style="display:block;margin-top:10px;font-size:.8rem;">Referencia o detalles del pago<textarea id="payment-details-${cardId}" rows="3" maxlength="4000" style="display:block;width:100%;margin-top:6px;border:1px solid #cbd5e1;border-radius:9px;padding:9px;font:inherit;resize:vertical;" placeholder="Introduce la referencia después de realizar el pago"></textarea></label><button type="button" class="btn-pay-submit" id="btn-pay-${cardId}" style="margin-top:10px;" onclick="submitBusinessPayment(${amount}, '${cardId}')">Enviar referencia para revisión</button><div id="status-box-${cardId}" class="pay-status-box hidden"></div>`;
    const cardEl = $(`pay-instructions-${cardId}`);
    cardEl.dataset.methods = JSON.stringify(methods.map(m => ({code:m.code,label:m.label})));
  } catch (err) {
    info.textContent = `No se pudieron consultar las instrucciones de pago: ${err.message}`;
  }
}

function escapeHtmlText(value) {
  return String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
}

async function submitBusinessPayment(amount, cardId) {
  const btn = $(`btn-pay-${cardId}`);
  const statusBox = $(`status-box-${cardId}`);
  const card = $(cardId);
  const referenceEl = $(`payment-details-${cardId}`);
  const details = String(referenceEl?.value || '').trim();
  if (!details) {
    if (statusBox) { statusBox.className = 'pay-status-box error'; statusBox.textContent = 'Introduce la referencia o los detalles del pago antes de enviarlos.'; }
    return;
  }
  let items = [];
  try { items = JSON.parse(card?.dataset.items || '[]'); } catch (e) {}
  const methodsEl = $(`pay-instructions-${cardId}`);
  let methods = [];
  try { methods = JSON.parse(methodsEl?.dataset.methods || '[]'); } catch (e) {}
  const method = String($(`payment-method-${cardId}`)?.value || methods[0]?.code || '');
  if (!method) { if (statusBox) { statusBox.className = 'pay-status-box error'; statusBox.textContent = 'Selecciona un método de cobro habilitado por el comercio.'; } return; }
  if (btn) { btn.disabled = true; btn.textContent = 'Enviando a revisión…'; }
  try {
    const res = await fetch('/api/v1/webchat/payment/request', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({amount, business_id:state.businessId, customer_id:state.customerId, payment_method:method, items, customer_payment_details:details})
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.detail || 'No se pudo registrar la solicitud de pago.');
    if (btn) btn.style.display = 'none';
    if (referenceEl) referenceEl.disabled = true;
    if (statusBox) { statusBox.className='pay-status-box pending'; statusBox.textContent=`Referencia recibida para USD ${amount.toFixed(2)}. El comercio debe verificar el pago y aprobar o rechazar la solicitud.`; }
    addMessage('bot', `Recibimos los datos de tu pago por USD ${amount.toFixed(2)}. La solicitud está pendiente de revisión del comercio.`);
    pollPaymentStatus(data.payment_id, cardId, amount);
  } catch(err) {
    if (btn) { btn.disabled = false; btn.textContent = 'Reintentar envío de referencia'; }
    if (statusBox) { statusBox.className='pay-status-box error'; statusBox.textContent=`Error: ${err.message}`; }
  }
}

function pollPaymentStatus(paymentId, cardId, amount) {
  let isFinished = false;
  let pollTimeout = null;

  async function check() {
    if (isFinished) return;
    try {
      const res = await fetch(`/api/v1/webchat/payment/status/${paymentId}?business_id=${encodeURIComponent(state.businessId)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === "approved" && !isFinished) {
          isFinished = true;
          if (pollTimeout) clearTimeout(pollTimeout);

          const statusBox = document.getElementById(`status-box-${cardId}`);
          if (statusBox) {
            statusBox.className = "pay-status-box approved";
            statusBox.innerHTML = `
              <div style="font-weight: 700; color: #166534;">✅ ¡Pago Aprobado con Éxito!</div>
              <div style="font-size: 0.8rem; color: #14532d;">Venta registrada por el comercio. Pedido confirmado.</div>
            `;
          }

          addMessage("bot", `🎉 ¡Tu pago de USD ${amount.toFixed(2)} ha sido APROBADO por el comercio! Tu pedido ya está confirmado y en preparación para entrega. ¡Muchas gracias por tu compra en ${state.bizName}!`);
          return;
        } else if (data.status === "rejected" && !isFinished) {
          isFinished = true;
          if (pollTimeout) clearTimeout(pollTimeout);

          const statusBox = document.getElementById(`status-box-${cardId}`);
          if (statusBox) {
            statusBox.className = "pay-status-box error";
            statusBox.innerHTML = `
              <div style="font-weight: 700; color: #991b1b;">❌ Solicitud Rechazada</div>
              <div style="font-size: 0.8rem; color: #7f1d1d;">El comercio ha rechazado este pago.</div>
            `;
          }

          addMessage("bot", `La solicitud de pago por USD ${amount.toFixed(2)} fue rechazada por el comercio. Por favor comunícate con atención al cliente para coordinar otro método de pago.`);
          return;
        }
      }
    } catch (e) {
      console.warn("Polling error:", e);
    }

    if (!isFinished) {
      pollTimeout = setTimeout(check, 1000);
    }
  }

  pollTimeout = setTimeout(check, 1000);
}

function setConnected(connected, label) {
  state.ready = connected;
  const statusEl = $("status");
  if (statusEl) statusEl.textContent = label;
  const inputEl = $("user-input");
  if (inputEl) inputEl.disabled = !connected;
  const btnEl = $("send-button");
  if (btnEl) btnEl.disabled = !connected;
}

function resetChatSession() {
  const messagesEl = $("messages");
  if (messagesEl) messagesEl.innerHTML = "";
  state.conversationId = null;
  state.customerId = null;
  initializeWebchat();
}

async function initializeWebchat() {
  try {
    const messagesEl = $("messages");
    if (messagesEl) messagesEl.innerHTML = "";

    const configUrl = state.businessId 
      ? `/api/v1/webchat/config?business_id=${encodeURIComponent(state.businessId)}`
      : "/api/v1/webchat/config";

    const configResponse = await fetch(configUrl, { cache: "no-store" });
    const config = await configResponse.json();
    if (!configResponse.ok) throw new Error(config.detail || "No se pudo cargar la configuración.");

    state.businessId = config.business?.id || state.businessId;
    state.bizName = config.business?.name || "Calyrisia Asesor";
    state.bizType = config.business?.business_type || "Comercio";

    // Anclar en localStorage y en la URL del navegador
    if (state.businessId) {
      localStorage.setItem("calyrisia_current_business_id", state.businessId);
      if (!urlParams.get("business_id")) {
        const cleanUrl = `${window.location.pathname}?business_id=${encodeURIComponent(state.businessId)}`;
        window.history.replaceState({ path: cleanUrl }, "", cleanUrl);
      }
    }

    updateHeaderUI();

    const sessionResponse = await fetch("/api/v1/webchat/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        business_id: state.businessId,
        customer_id: null,
        visitor_name: "Visitante Webchat",
      }),
    });
    const session = await sessionResponse.json();
    if (!sessionResponse.ok) throw new Error(session.detail || "No se pudo iniciar la sesión.");

    state.customerId = session.customer.id;
    setConnected(true, "En línea");
    addMessage("bot", `¡Hola! Soy el asesor de ${state.bizName}. ¿En qué te puedo ayudar hoy?`);
  } catch (error) {
    setConnected(false, "Sin negocio configurado");
    addMessage("bot", `No se pudo conectar con este negocio: ${error.message}. Abre el webchat desde el enlace correcto del negocio.`);
  }
}

async function sendMessage() {
  const inputEl = $("user-input");
  const btnEl = $("send-button");
  const typingEl = $("typing");
  const messagesEl = $("messages");
  
  if (!state.ready || !inputEl) return;
  const text = inputEl.value.trim();
  if (!text) return;

  addMessage("user", text);
  inputEl.value = "";
  inputEl.disabled = true;
  if (btnEl) btnEl.disabled = true;
  if (typingEl && messagesEl) {
    typingEl.style.display = "flex";
    messagesEl.appendChild(typingEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  try {
    const response = await fetch("/api/v1/webchat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        business_id: state.businessId,
        customer_id: state.customerId,
        conversation_id: state.conversationId,
        message: text,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Error procesando mensaje");

    state.conversationId = data.conversation_id;
    addMessage("bot", data.response || "No recibí una respuesta.");
    setConnected(true, "En línea");
  } catch (error) {
    addMessage("bot", error.message);
  } finally {
    if (typingEl) typingEl.style.display = "none";
    if (inputEl) {
      inputEl.disabled = false;
      inputEl.focus();
    }
    if (btnEl) btnEl.disabled = false;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const btn = $("send-button");
  if (btn) btn.addEventListener("click", sendMessage);
  const inp = $("user-input");
  if (inp) {
    inp.addEventListener("keypress", (e) => {
      if (e.key === "Enter") sendMessage();
    });
  }
  initializeWebchat();
});

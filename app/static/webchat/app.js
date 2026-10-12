const state = {
  customerId: localStorage.getItem("galaxy_webchat_customer_id") || null,
  conversationId: localStorage.getItem("galaxy_webchat_conversation_id") || null,
  ready: false,
};

const $ = (id) => document.getElementById(id);
const messages = $("messages");
const status = $("status");
const input = $("user-input");
const sendButton = $("send-button");
const typing = $("typing");

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function setConnected(connected, label) {
  state.ready = connected;
  status.textContent = label;
  input.disabled = !connected;
  sendButton.disabled = !connected;
}

async function initializeWebchat() {
  try {
    const configResponse = await fetch("/api/v1/webchat/config", { cache: "no-store" });
    const config = await configResponse.json();
    if (!configResponse.ok) throw new Error(config.detail || "No se pudo cargar la configuración del Webchat.");

    $("business-name").textContent = config.business?.name || "Galaxy Webchat";

    const sessionResponse = await fetch("/api/v1/webchat/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_id: state.customerId,
        visitor_name: "Visitante Webchat",
      }),
    });
    const session = await sessionResponse.json();
    if (!sessionResponse.ok) throw new Error(session.detail || "No se pudo iniciar el Webchat.");

    state.customerId = session.customer.id;
    localStorage.setItem("galaxy_webchat_customer_id", state.customerId);

    setConnected(true, "Conectado a Galaxy");
    addMessage("bot", `Hola. Soy el asistente de ${session.business?.name || "este negocio"}. ¿En qué puedo ayudarte?`);

    if (state.conversationId) {
      try {
        const historyResponse = await fetch(`/api/v1/webchat/history/${encodeURIComponent(state.conversationId)}`, { cache: "no-store" });
        const history = await historyResponse.json();
        if (historyResponse.ok) {
          messages.innerHTML = "";
          for (const item of history.conversation?.messages || []) {
            const role = item.sender_type === "customer" || item.direction === "inbound" ? "user" : "bot";
            addMessage(role, item.content || "");
          }
        } else {
          state.conversationId = null;
          localStorage.removeItem("galaxy_webchat_conversation_id");
        }
      } catch (_) {
        // Historial no disponible: la sesión sigue siendo válida.
      }
    }
  } catch (error) {
    setConnected(false, "No se pudo conectar");
    messages.innerHTML = "";
    addMessage("bot", error.message || "No se pudo iniciar el Webchat.");
  }
}

async function sendMessage() {
  if (!state.ready) return;
  const text = input.value.trim();
  if (!text) return;

  addMessage("user", text);
  input.value = "";
  input.disabled = true;
  sendButton.disabled = true;
  typing.style.display = "flex";
  messages.appendChild(typing);
  messages.scrollTop = messages.scrollHeight;

  try {
    const response = await fetch("/api/v1/webchat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_id: state.customerId,
        conversation_id: state.conversationId,
        message: text,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Galaxy no pudo procesar el mensaje.");

    state.conversationId = data.conversation_id;
    localStorage.setItem("galaxy_webchat_conversation_id", state.conversationId);
    addMessage("bot", data.response || "No recibí una respuesta.");
    status.textContent = "Conectado a Galaxy";
  } catch (error) {
    addMessage("bot", `Error: ${error.message}`);
    status.textContent = "Conectado · error de respuesta";
  } finally {
    typing.style.display = "none";
    input.disabled = false;
    sendButton.disabled = false;
    input.focus();
  }
}

sendButton.addEventListener("click", sendMessage);
input.addEventListener("keypress", (event) => {
  if (event.key === "Enter") sendMessage();
});

initializeWebchat();

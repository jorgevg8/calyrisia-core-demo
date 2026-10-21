const FALLBACK_PLANS = [
  {code:'emprendedor',label:'Emprendedor',price_usd:19,business_types:[
    {code:'sales_small',label:'Ventas y catálogo para negocio pequeño',description:'Pequeñas tiendas y emprendimientos que venden productos.',dashboard_label:'Inventario y catálogo'},
    {code:'appointments_small',label:'Citas y servicios independientes',description:'Profesionales independientes, salones pequeños y servicios por cita.',dashboard_label:'Agenda de citas'}
  ]},
  {code:'smart_business',label:'Smart Business',price_usd:49,business_types:[
    {code:'local_store',label:'Local comercial o tienda mediana',description:'Tiendas con inventario creciente.',dashboard_label:'Inventario y operación comercial'},
    {code:'bodega',label:'Bodegón o bodega mediana',description:'Catálogo más amplio y movimiento frecuente.',dashboard_label:'Inventario y operación comercial'},
    {code:'minimarket',label:'Minimarket',description:'Tienda de conveniencia con catálogo de tamaño medio.',dashboard_label:'Inventario y operación comercial'},
    {code:'restaurant',label:'Restaurante o cafetería',description:'Pedidos, menú, mesas y reservas.',dashboard_label:'Mesas y reservas'},
    {code:'consultorio',label:'Consultorio profesional',description:'Citas y seguimiento de atención.',dashboard_label:'Agenda de atención'},
    {code:'clinic',label:'Clínica o centro de salud',description:'Agenda de atención para servicios de salud.',dashboard_label:'Agenda de atención'},
    {code:'service_team',label:'Empresa de servicios con equipo',description:'Agendas y seguimiento para varios profesionales.',dashboard_label:'Agenda de citas y servicios'}
  ]}
];

const PLAN_BADGES = {emprendedor:'Para operaciones pequeñas',smart_business:'Para negocios en crecimiento',enterprise:'Para grandes operaciones'};
let planCatalog = FALLBACK_PLANS;
const onboardingParams = new URLSearchParams(window.location.search);
let planFilterCode = onboardingParams.get('plan') || '';
const checkoutRef = onboardingParams.get('ref') || '';
const checkoutMethod = onboardingParams.get('method') || '';
const checkoutJourneyLocked = Boolean(checkoutRef && ['emprendedor','smart_business'].includes(planFilterCode));
const PAYMENT_LABELS = {transferencia:'Transferencia bancaria',pago_movil:'Pago Móvil',binance:'Binance Pay',zinli:'Zinli',tarjeta:'Tarjeta bancaria'};
let checkoutPaymentVerified = false;

async function refreshCheckoutPaymentStatus() {
  if (!checkoutJourneyLocked || !checkoutRef) return;
  try {
    const response = await fetch(`/api/v1/public/checkout/status/${encodeURIComponent(checkoutRef)}`, {headers:{'Accept':'application/json'}});
    if (!response.ok) return;
    const record = await response.json();
    checkoutPaymentVerified = record.status === 'paid' && record.plan_code === planFilterCode;
    // Pre-fill buyer fields if empty
    const bName = document.getElementById('business_name');
    const oName = document.getElementById('owner_full_name');
    const oEmail = document.getElementById('owner_email');
    const oPhone = document.getElementById('owner_phone');
    if (bName && !bName.value && record.business_name) bName.value = record.business_name;
    if (oName && !oName.value && record.customer_name) oName.value = record.customer_name;
    if (oEmail && !oEmail.value && record.customer_email) oEmail.value = record.customer_email;
    if (oPhone && !oPhone.value && record.customer_phone) oPhone.value = record.customer_phone;
    if (checkoutPaymentVerified) {
      const status = document.getElementById('checkout-payment-status');
      if (status) status.textContent = 'Pago verificado y autorizado.';
      const context = document.getElementById('checkout-context');
      if (context && selectedPlan && selectedProfile) renderSelectedPlanStrip();
      const summaryStatus = document.getElementById('checkout-summary-payment-status');
      if (summaryStatus) summaryStatus.textContent = 'Pago verificado ✓';
    }
  } catch (_) {}
}

if (!checkoutJourneyLocked || !PAYMENT_LABELS[checkoutMethod]) {
  const requestedPlan = ['emprendedor','smart_business'].includes(planFilterCode) ? planFilterCode : 'emprendedor';
  window.location.replace(`/contratar/?plan=${encodeURIComponent(requestedPlan)}`);
  throw new Error('El onboarding debe abrirse desde un enlace de contratación válido.');
}

let selectedBusinessType = '';
let selectedPlan = null;
let selectedProfile = null;

function escapeHtml(value) {
  return String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
}

async function loadPlanOptions() {
  try {
    const response = await fetch('/api/v1/onboarding/catalog', {headers:{'Accept':'application/json'}});
    if (!response.ok) throw new Error('catalog unavailable');
    const data = await response.json();
    if (Array.isArray(data.plans) && data.plans.length) planCatalog = data.plans.filter(p => p.code !== 'enterprise');
  } catch (error) {
    console.info('Usando catálogo local del onboarding.', error);
  }
  renderPlanOptions();
}

function renderPlanOptions() {
  const root = document.getElementById('plan-options');
  if (!root) return;
  const visiblePlans = ['emprendedor','smart_business'].includes(planFilterCode)
    ? planCatalog.filter(plan => plan.code === planFilterCode)
    : planCatalog;
  const filterBanner = ['emprendedor','smart_business'].includes(planFilterCode)
    ? `<div class="plan-filter-banner"><span>Perfiles incluidos en tu plan <strong>${escapeHtml((planCatalog.find(p => p.code === planFilterCode) || {}).label || planFilterCode)}</strong> · Referencia: <strong>${escapeHtml(checkoutRef)}</strong>.</span><span class="plan-filter-lock">Pago verificado</span></div>`
    : '';
  root.innerHTML = filterBanner + visiblePlans.map(plan => {
    const featured = plan.code === 'smart_business';
    const categories = (plan.business_types || []).map(type => `
      <button type="button" class="business-choice ${selectedBusinessType === type.code ? 'selected' : ''}" data-business-type="${escapeHtml(type.code)}" onclick="selectBusinessType('${escapeHtml(type.code)}')">
        <span class="choice-indicator">${selectedBusinessType === type.code ? '✓' : '＋'}</span>
        <span class="choice-copy"><strong>${escapeHtml(type.label)}</strong><small>${escapeHtml(type.description || '')}</small><em>Módulo: ${escapeHtml(type.dashboard_label || 'Panel personalizado')}</em></span>
      </button>`).join('');
    return `<article class="plan-choice-card ${featured ? 'featured' : ''} ${selectedPlan?.code === plan.code ? 'plan-selected' : ''}">
      <div class="plan-card-top"><div><span class="plan-kicker">${escapeHtml(PLAN_BADGES[plan.code] || 'Plan CALYRISIA')}</span><h2>${escapeHtml(plan.label)}</h2></div><div class="plan-price"><strong>$${Number(plan.price_usd).toFixed(0)}</strong><small>USD / mes</small></div></div>
      <p class="plan-intro">Selecciona la actividad de tu negocio:</p>
      <div class="business-choice-list">${categories}</div>
    </article>`;
  }).join('');
  updateSelectedStatus();
}

function selectBusinessType(typeCode) {
  for (const plan of planCatalog) {
    const profile = (plan.business_types || []).find(item => item.code === typeCode);
    if (profile) {
      selectedBusinessType = typeCode;
      selectedPlan = plan;
      selectedProfile = profile;
      renderPlanOptions();
      updateSelectedStatus();
      break;
    }
  }
}

function updateSelectedStatus() {
  const status = document.getElementById('selection-status');
  const next = document.getElementById('continue-step-1');
  if (selectedProfile && selectedPlan) {
    status.innerHTML = `<span class="status-check">✓</span> Seleccionaste <strong>${escapeHtml(selectedProfile.label)}</strong> (${escapeHtml(selectedPlan.label)}).`;
    if (next) next.disabled = false;
  } else {
    status.textContent = 'Selecciona una actividad para continuar.';
    if (next) next.disabled = true;
  }
}

function nextStep(stepNumber) {
  if (stepNumber === 2 && (!selectedProfile || !selectedPlan)) return;
  document.querySelectorAll('.step').forEach(step => { step.classList.add('hidden'); step.classList.remove('active'); });
  const target = document.getElementById(`step-${stepNumber}`);
  if (target) { target.classList.remove('hidden'); target.classList.add('active'); }
  document.querySelectorAll('.step-dot').forEach(dot => dot.classList.remove('active','done'));
  for (let i=1;i<=3;i++) {
    const dot = document.getElementById(`stepper-${i}`);
    if (dot && i < stepNumber) dot.classList.add('done');
    if (dot && i === stepNumber) dot.classList.add('active');
  }
  if (stepNumber === 2) { renderSelectedPlanStrip(); generateBusinessAiPrompt(true); }
  window.scrollTo({top:0,behavior:'smooth'});
}
function prevStep(stepNumber) { nextStep(stepNumber); }


const BUSINESS_AI_PROMPTS = {
  sales_small: (name, currency) => `Eres el asistente oficial de ventas de ${name}.
OBJETIVO PRINCIPAL:
- Atender a los clientes con amabilidad, mostrar productos del catálogo con su precio exacto en ${currency} y cerrar ventas rápido.
FLUJO AUTOMÁTICO DE VENTAS:
1. Cuando el cliente pregunte por un producto, indícale precio, disponibilidad y opciones.
2. Si desea comprar, confirma los artículos, calcula el total en ${currency} e indícale los métodos de pago activos.
3. Pídele su comprobante o número de referencia para dejar el pago registrado como pendiente en el Dashboard y que el dueño solo tenga que aprobarlo.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario de atención: Lunes a Sábado de 8:00 am a 7:00 pm.
- Entregas / envíos: Coordinamos retiro en tienda o delivery local.`,

  appointments_small: (name, currency) => `Eres el asistente oficial de citas y atención de ${name}.
OBJETIVO PRINCIPAL:
- Orientar al cliente sobre los servicios disponibles, informar tarifas en ${currency} y agendar citas automáticamente sin perder el hilo de la conversación.
FLUJO AUTOMÁTICO DE CITAS:
1. Informa qué servicios ofrecemos y sus precios según el catálogo cargado en el Dashboard.
2. Para agendar una cita o consulta, solicita paso a paso: Nombre y apellido, Teléfono de contacto, Servicio deseado y Fecha/Hora preferida.
3. Apenas tengas esos datos, confirma y registra la cita automáticamente en el sistema para que aparezca en el Dashboard del dueño lista para aprobar o rechazar.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario de citas: Lunes a Sábado de 8:00 am a 6:00 pm.
- Ubicación / modalidad: Atención presencial previa cita confirmada.`,

  local_store: (name, currency) => `Eres el asesor comercial automatizado de ${name} (Tienda / Local Comercial).
OBJETIVO PRINCIPAL:
- Guiar al comprador por el catálogo, verificar stock en tiempo real, cotizar en ${currency} y procesar pedidos completos sin intervención manual.
FLUJO AUTOMÁTICO:
1. Consulta siempre el inventario activo antes de ofrecer un artículo y sugiere productos complementarios si hay stock.
2. Arma el carrito del cliente, confirma si requiere delivery o retiro en tienda y muestra los datos de pago.
3. Registra la referencia de pago para que el dueño la apruebe con un clic desde el Dashboard.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario de tienda: Lunes a Sábado de 9:00 am a 7:00 pm.
- Garantía y cambios: Según políticas vigentes del local.`,

  bodega: (name, currency) => `Eres el asistente de ventas rápidas de ${name} (Bodegón / Abasto).
OBJETIVO PRINCIPAL:
- Armar pedidos de combos, víveres, snacks y bebidas con rapidez, validando existencias y precios en ${currency}.
FLUJO AUTOMÁTICO:
1. Responde al instante qué productos hay disponibles y sus precios por unidad o combo.
2. Toma el pedido completo, solicita dirección de entrega si aplica y envía los métodos de pago (Pago Móvil, Binance, etc.).
3. Al recibir los datos del pago, regístralo en el panel de aprobaciones del Dashboard.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario: Todos los días de 9:00 am a 9:00 pm.
- Delivery: Disponible en toda la zona.`,

  minimarket: (name, currency) => `Eres el asistente digital de ${name} (Minimarket).
OBJETIVO PRINCIPAL:
- Ayudar a los clientes a hacer su mercado o compra rápida por chat, verificando stock y totalizando en ${currency}.
FLUJO AUTOMÁTICO:
1. Confirma disponibilidad de cada producto solicitado en la lista del cliente.
2. Calcula el monto total del pedido, solicita datos de entrega o retiro y comparte las instrucciones de cobro.
3. Registra el pago como pendiente para aprobación inmediata en el Dashboard.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario: Lunes a Domingo de 7:30 am a 9:00 pm.`,

  restaurant: (name, currency) => `Eres el anfitrión y tomador de pedidos automatizado de ${name} (Restaurante / Cafetería).
OBJETIVO PRINCIPAL:
- Mostrar el menú del día, tomar pedidos de comida o registrar reservas de mesa automáticamente en el Dashboard.
FLUJO AUTOMÁTICO DE RESERVAS Y PEDIDOS:
1. Si el cliente desea RESERVAR MESA: pídele Nombre completo, Teléfono, Cantidad de personas, Fecha/Hora y preferencias. Regístrala automáticamente en el Dashboard para que el dueño la apruebe o rechace.
2. Si el cliente desea PEDIR COMIDA (delivery o pickup): confirma los platos del menú, calcula el total en ${currency}, indica los métodos de pago y registra la referencia para aprobación.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario de cocina y reservas: Martes a Domingo de 12:00 pm a 10:30 pm.`,

  consultorio: (name, currency) => `Eres el asistente de recepción y agenda de ${name} (Consultorio Profesional).
OBJETIVO PRINCIPAL:
- Brindar información clara sobre las consultas y honorarios en ${currency}, y agendar pacientes/clientes automáticamente en el Dashboard.
FLUJO AUTOMÁTICO DE CONSULTAS:
1. Responde dudas sobre los tipos de consulta, preparación previa y tarifas registradas en el sistema.
2. Para agendar una consulta, solicita: Nombre completo del paciente/cliente, Teléfono, Motivo o tipo de consulta y Fecha/Hora solicitada.
3. Registra la consulta automáticamente como pendiente en el Dashboard para que el profesional solo tenga que aprobarla o reprogramarla.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario de consultas: Lunes a Viernes de 8:00 am a 5:00 pm.
- Recomendación: Llegar 10 minutos antes de la hora pautada.`,

  clinic: (name, currency) => `Eres la central inteligente de citas y orientación de ${name} (Clínica / Centro de Salud).
OBJETIVO PRINCIPAL:
- Informar especialidades, estudios y tarifas en ${currency}, y registrar citas médicas automáticamente en el Dashboard sin que el paciente se pierda.
FLUJO AUTOMÁTICO DE CITAS MÉDICAS:
1. Orienta con empatía y precisión sobre las especialidades y servicios disponibles en el centro (sin emitir diagnósticos médicos).
2. Para agendar cita o estudio, solicita: Nombre completo del paciente, Teléfono de contacto, Especialidad o servicio requerido y Fecha/Hora deseada.
3. Guarda la solicitud automáticamente en la bandeja de citas del Dashboard para que recepción o el médico la apruebe con un clic.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario de atención: Lunes a Sábado de 7:00 am a 6:00 pm.`,

  service_team: (name, currency) => `Eres el coordinador inteligente de servicios y citas de ${name}.
OBJETIVO PRINCIPAL:
- Cotizar servicios profesionales en ${currency} y agendar visitas, sesiones o atenciones del equipo directamente en el Dashboard.
FLUJO AUTOMÁTICO:
1. Explica el alcance y tarifa de cada servicio activo en el catálogo.
2. Solicita al cliente: Nombre completo, Teléfono, Servicio requerido, Fecha/Hora preferida y detalles o dirección.
3. Registra la cita automáticamente en el Dashboard en estado pendiente para que el dueño la apruebe y asigne.
PERSONALIZACIÓN (puedes editar o agregar aquí):
- Horario operativo: Lunes a Sábado de 8:00 am a 6:00 pm.`,

  supermarket: (name, currency) => `Eres el asistente omnicanal de ventas e inventario de ${name} (Supermercado).
OBJETIVO PRINCIPAL:
- Atender alto volumen de consultas de catálogo, precios en ${currency}, disponibilidad por departamento y pedidos completos.
FLUJO AUTOMÁTICO:
1. Verifica stock y precios exactos en el catálogo masivo antes de confirmar cada ítem.
2. Consolida listas de compra, totaliza el pedido e informa los métodos de pago autorizados.
3. Registra la solicitud de pago en el Centro de Aprobaciones del Dashboard.`,

  hypermarket: (name, currency) => `Eres el asistente corporativo de ventas masivas de ${name} (Hipermercado / Gran Superficie).
OBJETIVO PRINCIPAL:
- Gestionar consultas simultáneas de múltiples categorías, cotizaciones en ${currency}, disponibilidad de stock y cierre de órdenes.
FLUJO AUTOMÁTICO:
1. Consulta existencias reales, ofrece alternativas si un artículo tiene stock bajo y totaliza el carrito.
2. Envía instrucciones de pago y registra la referencia para validación en el Dashboard.`,

  large_store: (name, currency) => `Eres el asistente comercial de ${name} (Cadena / Tienda de Gran Formato).
OBJETIVO PRINCIPAL:
- Atender clientes con precisión sobre inventario, especificaciones, precios en ${currency} y procesamiento de compras.
FLUJO AUTOMÁTICO:
1. Confirma disponibilidad en catálogo, asesora en la selección y calcula el total.
2. Guía el pago y registra la operación en el Dashboard para aprobación ejecutiva.`,

  large_company: (name, currency) => `Eres el asistente comercial y operativo de ${name} (Empresa / Distribuidor).
OBJETIVO PRINCIPAL:
- Atender pedidos al mayor y detal, informar precios en ${currency}, validar stock disponible y canalizar pagos o agendamientos corporativos.
FLUJO AUTOMÁTICO:
1. Verifica catálogo y cantidades disponibles, arma la cotización u orden y envía los datos de cobro.
2. Registra pagos y solicitudes en el Dashboard para aprobación del equipo.`
};

function generateBusinessAiPrompt(onlyIfEmpty = false) {
  const textarea = document.getElementById('business_needs');
  const helper = document.getElementById('ai-prompt-helper');
  if (!textarea) return;
  if (onlyIfEmpty && textarea.value.trim()) return;
  const businessName = (document.getElementById('business_name')?.value || '').trim() || (selectedProfile ? selectedProfile.label : 'nuestro negocio');
  const currency = (document.getElementById('currency')?.value || 'USD').trim();
  const typeCode = selectedBusinessType || 'sales_small';
  const builder = BUSINESS_AI_PROMPTS[typeCode] || BUSINESS_AI_PROMPTS.sales_small;
  textarea.value = builder(businessName, currency);
  textarea.style.borderColor = '#00f2fe';
  textarea.style.boxShadow = '0 0 0 3px rgba(0, 242, 254, 0.18)';
  setTimeout(() => {
    textarea.style.borderColor = '';
    textarea.style.boxShadow = '';
  }, 1400);
  if (helper) {
    helper.innerHTML = `<span style="color:#38f9d7;font-weight:600;">✓ Prompt generado para ${escapeHtml(selectedProfile ? selectedProfile.label : typeCode)}.</span> Puedes agregarle o quitarle cualquier detalle antes de continuar.`;
  }
}

function renderSelectedPlanStrip() {
  const strip = document.getElementById('selected-plan-strip');
  if (!strip || !selectedProfile || !selectedPlan) return;
  strip.innerHTML = `<div class="strip-icon">✦</div><div><strong>${escapeHtml(selectedProfile.label)}</strong><small>${escapeHtml(selectedProfile.dashboard_label || 'Panel personalizado')}</small></div><div class="strip-price"><strong>$${Number(selectedPlan.price_usd).toFixed(0)}</strong><small>USD/mes</small></div>`;
  const context = document.getElementById('checkout-context');
  if (context && checkoutJourneyLocked) {
    const method = PAYMENT_LABELS[checkoutMethod] || checkoutMethod;
    context.hidden = false;
    context.innerHTML = `Referencia: <strong>${escapeHtml(checkoutRef)}</strong> · Método: <strong>${escapeHtml(method)}</strong> · <span id="checkout-payment-status" style="color:#38f9d7;font-weight:700">Pago aprobado ✓</span>`;
  }
}

function readRequest() {
  const name = document.getElementById('business_name').value.trim();
  const owner = document.getElementById('owner_full_name').value.trim();
  const phone = document.getElementById('owner_phone').value.trim();
  const email = document.getElementById('owner_email').value.trim().toLowerCase();
  const password = document.getElementById('owner_password').value;
  const passwordConfirm = document.getElementById('owner_password_confirm').value;
  if (!selectedProfile || !selectedPlan) throw new Error('Selecciona primero una actividad compatible.');
  if (!name) throw new Error('Escribe el nombre del negocio.');
  if (!owner) throw new Error('Escribe tu nombre y apellido.');
  if (!phone) throw new Error('Escribe tu teléfono o WhatsApp.');
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Escribe un correo electrónico válido para tu usuario del Dashboard.');
  if (!password || password.length < 8) throw new Error('La contraseña debe tener al menos 8 caracteres.');
  if (password !== passwordConfirm) throw new Error('Las contraseñas no coinciden. Verifícalas.');
  return {
    businessName: name,
    owner,
    email,
    password,
    phone,
    currency: document.getElementById('currency').value,
    timezone: document.getElementById('timezone').value,
    needs: document.getElementById('business_needs').value.trim()
  };
}

function prepareRequest() {
  let request;
  try { request = readRequest(); } catch (error) { alert(error.message); return; }
  const errBox = document.getElementById('onboarding-error');
  if (errBox) errBox.hidden = true;
  const summary = document.getElementById('request-summary');
  summary.innerHTML = `
    <div class="summary-plan"><div><span class="summary-eyebrow">CUENTA LISTA PARA ACTIVAR</span><h2>${escapeHtml(request.businessName)}</h2><p>${escapeHtml(selectedProfile.label)} · ${escapeHtml(selectedPlan.label)}</p></div><div class="summary-amount"><strong>$${Number(selectedPlan.price_usd).toFixed(0)}</strong><small>USD / mes</small></div></div>
    <div class="summary-grid">
      <div><small>Usuario de acceso al Dashboard</small><strong>${escapeHtml(request.email)}</strong></div>
      <div><small>Contraseña configurada</small><strong>•••••••• (${request.password.length} caracteres)</strong></div>
      <div><small>Propietario</small><strong>${escapeHtml(request.owner)}</strong></div>
      <div><small>Teléfono</small><strong>${escapeHtml(request.phone)}</strong></div>
      <div><small>Panel asignado</small><strong>${escapeHtml(selectedProfile.dashboard_label || 'Panel Ejecutivo')}</strong></div>
      <div><small>Moneda / Zona horaria</small><strong>${escapeHtml(request.currency)} · ${escapeHtml(request.timezone)}</strong></div>
    </div>`;
  nextStep(3);
}

async function submitOnboardingAndEnterDashboard() {
  let req;
  try { req = readRequest(); } catch (error) { alert(error.message); return; }
  const btn = document.getElementById('createBusinessBtn');
  const editBtn = document.getElementById('editOnboardingBtn');
  const errBox = document.getElementById('onboarding-error');
  if (errBox) errBox.hidden = true;
  btn.disabled = true;
  if (editBtn) editBtn.disabled = true;
  const origText = btn.innerHTML;
  btn.innerHTML = 'Creando tu negocio y preparando el Dashboard…';

  try {
    const response = await fetch('/api/v1/onboarding/business', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: JSON.stringify({
        checkout_ref: checkoutRef,
        business_name: req.businessName,
        business_type: selectedBusinessType,
        plan_code: selectedPlan.code,
        ai_prompt: req.needs || null,
        currency: req.currency,
        owner_email: req.email,
        owner_password: req.password,
        owner_full_name: req.owner,
        owner_phone: req.phone
      })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || 'No se pudo completar la creación del negocio.');
    }
    if (data.access_token) {
      localStorage.setItem('galaxy_access_token', data.access_token);
      localStorage.setItem('galaxy_role', 'OWNER');
    }
    btn.innerHTML = '¡Cuenta creada! Entrando a tu Dashboard →';
    window.location.assign('/dashboard/');
  } catch (err) {
    if (errBox) {
      errBox.textContent = err.message;
      errBox.hidden = false;
    } else {
      alert(err.message);
    }
    btn.disabled = false;
    if (editBtn) editBtn.disabled = false;
    btn.innerHTML = origText;
  }
}

loadPlanOptions();
refreshCheckoutPaymentStatus();

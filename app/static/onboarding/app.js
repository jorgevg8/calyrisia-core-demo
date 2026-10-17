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
  ]},
  {code:'enterprise',label:'Enterprise',price_usd:99,business_types:[
    {code:'supermarket',label:'Supermercado',description:'Catálogo amplio y operación con alto volumen.',dashboard_label:'Operación de alto volumen'},
    {code:'hypermarket',label:'Hipermercado o gran superficie',description:'Amplio inventario y operación de ventas masivas.',dashboard_label:'Operación de alto volumen'},
    {code:'large_store',label:'Tienda grande o cadena de tiendas',description:'Operaciones grandes y múltiples ubicaciones.',dashboard_label:'Operación de alto volumen'},
    {code:'large_company',label:'Empresa o distribuidor de alto volumen',description:'Equipos, procesos complejos y grandes volúmenes.',dashboard_label:'Operación empresarial'}
  ]}
];

const CONTACT_WHATSAPP = '584128418550';
const CONTACT_EMAIL = 'jorge@calyrisia.com';
const PLAN_BADGES = {emprendedor:'Para operaciones pequeñas',smart_business:'Para negocios en crecimiento',enterprise:'Para grandes operaciones'};
let planCatalog = FALLBACK_PLANS;
const onboardingParams = new URLSearchParams(window.location.search);
let planFilterCode = onboardingParams.get('plan') || '';
const checkoutRef = onboardingParams.get('ref') || '';
const checkoutMethod = onboardingParams.get('method') || '';
const checkoutJourneyLocked = Boolean(checkoutRef && ['emprendedor','smart_business','enterprise'].includes(planFilterCode));
const PAYMENT_LABELS = {transferencia:'Transferencia bancaria',pago_movil:'Pago Móvil',binance:'Binance Pay',zinli:'Zinli',tarjeta:'Tarjeta bancaria'};
let checkoutPaymentVerified = false;
async function refreshCheckoutPaymentStatus() {
  if (!checkoutJourneyLocked || !checkoutRef) return;
  try {
    const response = await fetch(`/api/v1/public/checkout/status/${encodeURIComponent(checkoutRef)}`, {headers:{'Accept':'application/json'}});
    if (!response.ok) return;
    const record = await response.json();
    checkoutPaymentVerified = record.status === 'paid' && record.plan_code === planFilterCode && record.payment_method === checkoutMethod;
    if (checkoutPaymentVerified) {
      const status = document.getElementById('checkout-payment-status');
      if (status) status.textContent = 'Pago con tarjeta verificado por el proveedor.';
      const context = document.getElementById('checkout-context');
      if (context && selectedPlan && selectedProfile) renderSelectedPlanStrip();
      const summaryStatus = document.getElementById('checkout-summary-payment-status');
      if (summaryStatus) summaryStatus.textContent = 'Pago verificado';
    }
  } catch (_) {}
}
if (!checkoutJourneyLocked || !PAYMENT_LABELS[checkoutMethod]) {
  const requestedPlan = ['emprendedor','smart_business','enterprise'].includes(planFilterCode) ? planFilterCode : 'emprendedor';
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
    if (Array.isArray(data.plans) && data.plans.length) planCatalog = data.plans;
  } catch (error) {
    console.info('Usando catálogo local del onboarding.', error);
  }
  renderPlanOptions();
}

function renderPlanOptions() {
  const root = document.getElementById('plan-options');
  if (!root) return;
  const visiblePlans = ['emprendedor','smart_business','enterprise'].includes(planFilterCode)
    ? planCatalog.filter(plan => plan.code === planFilterCode)
    : planCatalog;
  const filterBanner = ['emprendedor','smart_business','enterprise'].includes(planFilterCode)
    ? `<div class="plan-filter-banner"><span>Estás viendo perfiles compatibles con <strong>${escapeHtml((planCatalog.find(p => p.code === planFilterCode) || {}).label || planFilterCode)}</strong>${checkoutJourneyLocked ? ` · Referencia: <strong>${escapeHtml(checkoutRef)}</strong>` : ''}.</span>${checkoutJourneyLocked ? '<span class="plan-filter-lock">Plan asociado a tu proceso de contratación</span>' : '<button type="button" onclick="clearPlanFilter()">Comparar todos los planes</button>'}</div>`
    : '';
  root.innerHTML = filterBanner + visiblePlans.map(plan => {
    const featured = plan.code === 'smart_business';
    const categories = (plan.business_types || []).map(type => `
      <button type="button" class="business-choice ${selectedBusinessType === type.code ? 'selected' : ''}" data-business-type="${escapeHtml(type.code)}" onclick="selectBusinessType('${escapeHtml(type.code)}')">
        <span class="choice-indicator">${selectedBusinessType === type.code ? '✓' : '＋'}</span>
        <span class="choice-copy"><strong>${escapeHtml(type.label)}</strong><small>${escapeHtml(type.description || '')}</small><em>Dashboard: ${escapeHtml(type.dashboard_label || 'Panel personalizado')}</em></span>
      </button>`).join('');
    return `<article class="plan-choice-card ${featured ? 'featured' : ''} ${selectedPlan?.code === plan.code ? 'plan-selected' : ''}">
      ${featured ? '<span class="popular-tag">RECOMENDADO PARA NEGOCIOS EN CRECIMIENTO</span>' : ''}
      <div class="plan-card-top"><div><span class="plan-kicker">${escapeHtml(PLAN_BADGES[plan.code] || 'Plan CALYRISIA')}</span><h2>${escapeHtml(plan.label)}</h2></div><div class="plan-price"><strong>$${Number(plan.price_usd).toFixed(0)}</strong><small>USD / mes</small></div></div>
      <p class="plan-intro">Selecciona el tipo de negocio que corresponde a este plan.</p>
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

function clearPlanFilter() {
  if (checkoutJourneyLocked) return;
  planFilterCode = '';
  const cleanUrl = `${window.location.pathname}${window.location.hash || ''}`;
  window.history.replaceState({}, '', cleanUrl);
  renderPlanOptions();
}

function updateSelectedStatus() {
  const status = document.getElementById('selection-status');
  const next = document.getElementById('continue-step-1');
  if (selectedProfile && selectedPlan) {
    status.innerHTML = `<span class="status-check">✓</span> Seleccionaste <strong>${escapeHtml(selectedProfile.label)}</strong>. Plan compatible: <strong>${escapeHtml(selectedPlan.label)} · $${Number(selectedPlan.price_usd).toFixed(0)}/mes</strong>.`;
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
  if (stepNumber === 2) renderSelectedPlanStrip();
  window.scrollTo({top:0,behavior:'smooth'});
}
function prevStep(stepNumber) { nextStep(stepNumber); }

function renderSelectedPlanStrip() {
  const strip = document.getElementById('selected-plan-strip');
  if (!strip || !selectedProfile || !selectedPlan) return;
  strip.innerHTML = `<div class="strip-icon">✦</div><div><strong>${escapeHtml(selectedProfile.label)}</strong><small>${escapeHtml(selectedProfile.dashboard_label || 'Panel personalizado')}</small></div><div class="strip-price"><strong>$${Number(selectedPlan.price_usd).toFixed(0)}</strong><small>USD/mes</small></div>`;
  const context = document.getElementById('checkout-context');
  if (context && checkoutJourneyLocked) {
    const method = PAYMENT_LABELS[checkoutMethod] || 'Por confirmar';
    context.hidden = false;
    context.innerHTML = `<strong>Proceso de contratación asociado.</strong><br>Referencia: <strong>${escapeHtml(checkoutRef)}</strong> · Método: <strong>${escapeHtml(method)}</strong>.<br><span id="checkout-payment-status">${checkoutPaymentVerified ? 'Pago con tarjeta verificado por el proveedor.' : (checkoutMethod === 'tarjeta' ? 'Consultando confirmación del pago…' : 'El comprobante de este método requiere revisión manual.')}</span>`;
  }
}

function readRequest() {
  const name = document.getElementById('business_name').value.trim();
  const owner = document.getElementById('owner_full_name').value.trim();
  const email = document.getElementById('owner_email').value.trim();
  if (!selectedProfile || !selectedPlan) throw new Error('Selecciona primero una actividad compatible.');
  if (!name) throw new Error('Escribe el nombre del negocio.');
  if (!owner) throw new Error('Escribe tu nombre.');
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Escribe un correo de contacto válido.');
  const channels = Array.from(document.querySelectorAll('input[name="channels"]:checked')).map(el => el.value);
  return {
    businessName:name, owner, email,
    phone:document.getElementById('owner_phone').value.trim(),
    currency:document.getElementById('currency').value,
    timezone:document.getElementById('timezone').value,
    needs:document.getElementById('business_needs').value.trim(),
    channels
  };
}

function prepareRequest() {
  let request;
  try { request = readRequest(); } catch (error) { alert(error.message); return; }
  const channelText = request.channels.length ? request.channels.join(', ') : 'Por definir con CALYRISIA';
  const summary = document.getElementById('request-summary');
  summary.innerHTML = `
    <div class="summary-plan"><div><span class="summary-eyebrow">PLAN COMPATIBLE</span><h2>${escapeHtml(selectedPlan.label)}</h2><p>${escapeHtml(selectedProfile.description || '')}</p></div><div class="summary-amount"><strong>$${Number(selectedPlan.price_usd).toFixed(0)}</strong><small>USD / mes</small></div></div>
    <div class="summary-grid">
      <div><small>Negocio</small><strong>${escapeHtml(request.businessName)}</strong></div>
      <div><small>Dashboard inicial</small><strong>${escapeHtml(selectedProfile.dashboard_label || 'Panel personalizado')}</strong></div>
      <div><small>Contacto</small><strong>${escapeHtml(request.owner)} · ${escapeHtml(request.email)}</strong></div>
      <div><small>Canales de interés</small><strong>${escapeHtml(channelText)}</strong></div>
      <div><small>Moneda</small><strong>${escapeHtml(request.currency)}</strong></div>
      <div><small>Zona horaria</small><strong>${escapeHtml(request.timezone)}</strong></div>
      ${checkoutJourneyLocked ? `<div><small>Referencia de contratación</small><strong>${escapeHtml(checkoutRef)}</strong></div><div><small>Método de pago</small><strong id="checkout-summary-payment-status">${checkoutPaymentVerified ? 'Pago verificado' : `${escapeHtml(PAYMENT_LABELS[checkoutMethod] || 'Por confirmar')} · pendiente de validar`}</strong></div>` : ''}
      ${request.phone ? `<div class="summary-wide"><small>WhatsApp</small><strong>${escapeHtml(request.phone)}</strong></div>` : ''}
      ${request.needs ? `<div class="summary-wide"><small>Prioridad del negocio</small><strong>${escapeHtml(request.needs)}</strong></div>` : ''}
    </div>`;
  nextStep(3);
}

function composeMessage() {
  const r = readRequest();
  const channelText = r.channels.length ? r.channels.join(', ') : 'Por definir';
  return [
    'Hola CALYRISIA, quiero solicitar una propuesta para mi negocio.',
    '',
    `Plan compatible: ${selectedPlan.label} — $${Number(selectedPlan.price_usd).toFixed(0)} USD/mes.`,
    `Tipo de negocio: ${selectedProfile.label} (${selectedBusinessType}).`,
    `Dashboard requerido: ${selectedProfile.dashboard_label || 'Panel personalizado'}.`,
    `Negocio: ${r.businessName}`,
    `Contacto: ${r.owner}`,
    `Correo: ${r.email}`,
    r.phone ? `WhatsApp: ${r.phone}` : '',
    `Canales de interés: ${channelText}`,
    `Moneda: ${r.currency}`,
    `Zona horaria: ${r.timezone}`,
    checkoutJourneyLocked ? `Referencia de contratación: ${checkoutRef}` : '',
    checkoutJourneyLocked ? `Método de pago indicado: ${PAYMENT_LABELS[checkoutMethod] || 'Por confirmar'} (${checkoutPaymentVerified ? 'pago de tarjeta verificado por el proveedor' : 'pendiente de revisión; no afirmar como pagado'})` : '',
    r.needs ? `Prioridad: ${r.needs}` : '',
    '',
    'Entiendo que la activación y la configuración se confirman con CALYRISIA antes de empezar.'
  ].filter(Boolean).join('\n');
}

function sendWhatsAppRequest() {
  try {
    const message = composeMessage();
    window.open(`https://wa.me/${CONTACT_WHATSAPP}?text=${encodeURIComponent(message)}`, '_blank', 'noopener,noreferrer');
  } catch (error) { alert(error.message); }
}
function sendEmailRequest() {
  try {
    const message = composeMessage();
    const subject = `Solicitud CALYRISIA - ${selectedPlan.label} - ${document.getElementById('business_name').value.trim()}`;
    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(message)}`;
  } catch (error) { alert(error.message); }
}

loadPlanOptions();
refreshCheckoutPaymentStatus();

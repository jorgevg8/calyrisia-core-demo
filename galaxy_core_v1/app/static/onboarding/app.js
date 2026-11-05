const FALLBACK_BUSINESS_TYPES = [
  {code:'tech_store',label:'Tienda de tecnología y electrónica',description:'Equipos, accesorios, modelos, garantías y stock en vivo.',dashboard_label:'Inventario, variantes y pedidos'},
  {code:'clothing_store',label:'Tienda de ropa, calzado y moda',description:'Prendas, tallas, colores disponibles y armado de pedidos.',dashboard_label:'Catálogo, tallas y pedidos'},
  {code:'distributor',label:'Distribuidora o mayorista comercial',description:'Cotización por unidad, caja o bulto y seguimiento B2B.',dashboard_label:'Catálogo mayorista y pedidos'},
  {code:'auto_parts',label:'Repuestos automotrices y accesorios',description:'Búsqueda por código SKU, marca, compatibilidad y stock.',dashboard_label:'Repuestos, SKU y pedidos'},
  {code:'hardware_store',label:'Ferretería y materiales',description:'Herramientas, materiales, medidas y cotización rápida.',dashboard_label:'Inventario y cotizaciones'},
  {code:'variety_store',label:'Tienda de productos variados',description:'Artículos de hogar, regalos y mercancía general en vivo.',dashboard_label:'Inventario y ventas'},
  {code:'bodega',label:'Bodegón, minimarket o abasto',description:'Alimentos, bebidas y productos de alta rotación con delivery.',dashboard_label:'Inventario y pedidos rápidos'},
  {code:'restaurant',label:'Restaurante o gastronomía',description:'Menú digital, pedidos para delivery y reservas de mesa.',dashboard_label:'Menú, pedidos y reservas'},
  {code:'appointments_small',label:'Servicios y agenda de citas',description:'Consultorios, estética y talleres con agenda automática.',dashboard_label:'Agenda de citas y servicios'}
];

const FALLBACK_PLANS = [
  {code:'free',label:'Plan Free',price_usd:0,badge:'Comienza gratis hoy mismo sin tarjeta ni pago previo',business_types:FALLBACK_BUSINESS_TYPES},
  {code:'pro',label:'Plan PRO',price_usd:39,badge:'Inteligencia empresarial completa, WhatsApp QR, CRM y Business Radar',business_types:FALLBACK_BUSINESS_TYPES}
];

const PLAN_BADGES = {
  free:'Comienza gratis · $0 / mes · Sin pago previo',
  pro:'Producto comercial principal · Inteligencia y operación autónoma'
};

let planCatalog = FALLBACK_PLANS;
const onboardingParams = new URLSearchParams(window.location.search);
const rawPlanParam = (onboardingParams.get('plan') || 'free').trim().toLowerCase();
let planFilterCode = ['pro','smart_business','enterprise'].includes(rawPlanParam) ? 'pro' : 'free';
const checkoutRef = (onboardingParams.get('ref') || '').trim().toUpperCase();
const checkoutMethod = (onboardingParams.get('method') || '').trim().toLowerCase();
const PAYMENT_LABELS = {transferencia:'Transferencia bancaria',pago_movil:'Pago Móvil',binance:'Binance Pay',zinli:'Zinli',tarjeta:'Tarjeta bancaria'};

// If user requested PRO without a checkoutRef, redirect them to /contratar/?plan=pro
if (planFilterCode === 'pro' && !checkoutRef) {
  window.location.replace('/contratar/?plan=pro');
  throw new Error('Redirigiendo al portal de contratación PRO.');
}

const checkoutJourneyLocked = Boolean(checkoutRef && planFilterCode === 'pro');
let checkoutPaymentVerified = false;

async function refreshCheckoutPaymentStatus() {
  if (!checkoutJourneyLocked || !checkoutRef) return;
  try {
    const response = await fetch(`/api/v1/public/checkout/status/${encodeURIComponent(checkoutRef)}`, {headers:{'Accept':'application/json'}});
    if (!response.ok) return;
    const record = await response.json();
    checkoutPaymentVerified = record.status === 'paid';
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
    if (Array.isArray(data.plans) && data.plans.length) {
      planCatalog = data.plans;
    }
  } catch (error) {
    console.info('Usando catálogo local del onboarding.', error);
  }
  renderPlanOptions();
}

function renderPlanOptions() {
  const root = document.getElementById('plan-options');
  if (!root) return;
  const visiblePlans = planCatalog.filter(plan => plan.code === planFilterCode);
  const activePlans = visiblePlans.length ? visiblePlans : [planCatalog[0]];

  let filterBanner = '';
  if (planFilterCode === 'pro' && checkoutRef) {
    filterBanner = `<div class="plan-filter-banner"><span>Activando <strong>Plan PRO</strong> · Referencia verificada: <strong>${escapeHtml(checkoutRef)}</strong>.</span><span class="plan-filter-lock">Pago verificado ✓</span></div>`;
  } else {
    filterBanner = `<div class="plan-filter-banner" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
      <span>Estás creando tu cuenta en el <strong>Plan Free ($0/mes)</strong> · Sin tarjeta ni pago previo.</span>
      <a href="/contratar/?plan=pro" style="color:#00f2fe;font-size:.8rem;font-weight:700;text-decoration:underline;">¿Prefieres activar directo el Plan PRO? Contratar PRO →</a>
    </div>`;
  }

  root.innerHTML = filterBanner + activePlans.map(plan => {
    const featured = plan.code === 'pro';
    const categories = (plan.business_types || []).map(type => `
      <button type="button" class="business-choice ${selectedBusinessType === type.code && selectedPlan?.code === plan.code ? 'selected' : ''}" data-business-type="${escapeHtml(type.code)}" onclick="selectBusinessType('${escapeHtml(type.code)}', '${escapeHtml(plan.code)}')">
        <span class="choice-indicator">${selectedBusinessType === type.code && selectedPlan?.code === plan.code ? '✓' : '＋'}</span>
        <span class="choice-copy"><strong>${escapeHtml(type.label)}</strong><small>${escapeHtml(type.description || '')}</small><em>Módulo: ${escapeHtml(type.dashboard_label || 'Panel personalizado')}</em></span>
      </button>`).join('');
    return `<article class="plan-choice-card ${featured ? 'featured' : ''} ${selectedPlan?.code === plan.code ? 'plan-selected' : ''}">
      <div class="plan-card-top"><div><span class="plan-kicker">${escapeHtml(PLAN_BADGES[plan.code] || plan.badge || 'Plan CALYRISIA')}</span><h2>${escapeHtml(plan.label)}</h2></div><div class="plan-price"><strong>$${Number(plan.price_usd).toFixed(0)}</strong><small>USD / mes</small></div></div>
      <p class="plan-intro">Selecciona el sector o actividad principal de tu negocio:</p>
      <div class="business-choice-list">${categories}</div>
    </article>`;
  }).join('');
  updateSelectedStatus();
}

function selectBusinessType(typeCode, planCode = null) {
  const targetPlanCode = planCode || planFilterCode || 'free';
  const plan = planCatalog.find(p => p.code === targetPlanCode) || planCatalog[0];
  if (!plan) return;
  const profile = (plan.business_types || []).find(item => item.code === typeCode);
  if (profile) {
    selectedBusinessType = typeCode;
    selectedPlan = plan;
    selectedProfile = profile;
    renderPlanOptions();
    updateSelectedStatus();
  }
}

function updateSelectedStatus() {
  const status = document.getElementById('selection-status');
  const next = document.getElementById('continue-step-1');
  if (selectedProfile && selectedPlan) {
    status.innerHTML = `<span class="status-check">✓</span> Seleccionaste <strong>${escapeHtml(selectedProfile.label)}</strong> (${escapeHtml(selectedPlan.label)} · $${Number(selectedPlan.price_usd).toFixed(0)}/mes).`;
    if (next) next.disabled = false;
  } else {
    status.textContent = 'Selecciona el giro de tu negocio para continuar.';
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
  tech_store: (name, currency) => `Eres el asesor especialista en tecnología y electrónica de ${name}.
OBJETIVO PRINCIPAL:
- Atender consultas de clientes sobre equipos, accesorios, modelos, capacidades y garantías, informando precios exactos en ${currency} y stock real.
FLUJO AUTOMÁTICO DE VENTAS:
1. Cuando el cliente consulte un equipo o accesorio, confirma precio en ${currency}, disponibilidad real y variantes (capacidad, color, modelo).
2. Si desea comprar, confirma los artículos y cantidades, calcula el total en ${currency}, pregunta si prefiere delivery o retiro en tienda y muestra los métodos de pago activos.
3. Solicita el número de referencia del pago para registrarlo en el Centro de Aprobaciones del propietario.
PERSONALIZACIÓN:
- Horario: Lunes a Sábado de 9:00 am a 7:00 pm.
- Garantía: Todos los equipos cuentan con garantía verificada por defecto de fábrica.`,

  clothing_store: (name, currency) => `Eres el asesor de moda y ventas de ${name}.
OBJETIVO PRINCIPAL:
- Guiar a los clientes por el catálogo de ropa, calzado y accesorios, confirmando tallas, colores disponibles y precios en ${currency}.
FLUJO AUTOMÁTICO DE VENTAS:
1. Informa precio exacto y verifica que la talla o color solicitado esté disponible en el inventario activo.
2. Arma el pedido completo del cliente, calcula el total en ${currency} e indica las instrucciones de pago configuradas.
3. Registra la referencia de pago como pendiente para validación del dueño en el Dashboard.
PERSONALIZACIÓN:
- Horario: Lunes a Sábado de 9:30 am a 7:30 pm.
- Envíos y cambios: Retiro en tienda, delivery local y envíos nacionales.`,

  distributor: (name, currency) => `Eres el ejecutivo comercial automatizado de ${name} (Distribuidora / Mayorista).
OBJETIVO PRINCIPAL:
- Atender comerciantes y compradores al mayor o detal, informando precios en ${currency}, presentaciones (unidad, caja, bulto) y stock disponible en tiempo real.
FLUJO AUTOMÁTICO DE COTIZACIÓN Y PEDIDOS:
1. Verifica existencias y precios oficiales según los productos y presentaciones del catálogo.
2. Prepara el resumen de la orden con cantidades y subtotales en ${currency}, e informa los métodos de pago autorizados.
3. Registra la referencia del pago o la solicitud comercial para aprobación y despacho desde el Dashboard.
PERSONALIZACIÓN:
- Horario de despacho: Lunes a Viernes de 8:00 am a 5:30 pm y Sábados de 8:00 am a 1:00 pm.`,

  auto_parts: (name, currency) => `Eres el especialista técnico de repuestos automotrices de ${name}.
OBJETIVO PRINCIPAL:
- Ayudar al cliente a ubicar el repuesto, lubricante o batería exacta por nombre, marca o código SKU, indicando precio en ${currency} y stock en vivo.
FLUJO AUTOMÁTICO:
1. Confirma disponibilidad, marca, compatibilidad y precio en ${currency} según el catálogo oficial.
2. Si el cliente confirma la compra, totaliza el pedido, consulta si retira en tienda o requiere envío y muestra los datos de pago.
3. Registra la referencia de pago en el Dashboard para validación del propietario.
PERSONALIZACIÓN:
- Horario: Lunes a Sábado de 8:00 am a 6:00 pm.`,

  hardware_store: (name, currency) => `Eres el asesor ferretero y de materiales de ${name}.
OBJETIVO PRINCIPAL:
- Cotizar herramientas, materiales eléctricos, plomería, pinturas y suministros con precios exactos en ${currency} y disponibilidad inmediata.
FLUJO AUTOMÁTICO:
1. Responde al instante qué artículos están disponibles en inventario, sus medidas/marcas y precio unitario en ${currency}.
2. Consolida la lista de materiales del cliente, calcula el monto total e indica los métodos de cobro activos.
3. Registra el pago como pendiente en el Dashboard para que el dueño autorice el despacho.
PERSONALIZACIÓN:
- Horario: Lunes a Sábado de 8:00 am a 6:00 pm.`,

  variety_store: (name, currency) => `Eres el asistente comercial de ${name} (Tienda de Productos Variados).
OBJETIVO PRINCIPAL:
- Atender consultas de catálogo con rapidez, mostrar opciones disponibles con precios en ${currency} y preparar pedidos completos sin demora.
FLUJO AUTOMÁTICO:
1. Informa precio y stock real de cada artículo consultado y sugiere opciones complementarias disponibles.
2. Calcula el total del pedido en ${currency}, confirma modalidad de entrega y comparte los métodos de pago.
3. Registra el comprobante o referencia en el Centro de Aprobaciones del Dashboard.
PERSONALIZACIÓN:
- Horario: Lunes a Sábado de 9:00 am a 7:00 pm.`,

  bodega: (name, currency) => `Eres el asistente de ventas rápidas de ${name} (Bodegón / Minimarket).
OBJETIVO PRINCIPAL:
- Armar pedidos de alimentos, bebidas, snacks y combos con rapidez, validando existencias reales y precios en ${currency}.
FLUJO AUTOMÁTICO:
1. Responde al instante qué productos hay disponibles y sus precios en ${currency}.
2. Toma el pedido completo, solicita dirección de delivery o retiro y envía los métodos de pago configurados.
3. Al recibir la referencia de pago, regístrala en el panel de aprobaciones del Dashboard.
PERSONALIZACIÓN:
- Horario: Todos los días de 8:30 am a 9:00 pm.`,

  sales_small: (name, currency) => `Eres el asistente oficial de ventas de ${name}.
OBJETIVO PRINCIPAL:
- Atender a los clientes con amabilidad, mostrar productos del catálogo con su precio exacto en ${currency} y preparar pedidos rápido.
FLUJO AUTOMÁTICO DE VENTAS:
1. Cuando el cliente pregunte por un producto, indícale precio, disponibilidad y opciones.
2. Si desea comprar, confirma los artículos, calcula el total en ${currency} e indícale los métodos de pago activos.
3. Pídele su número de referencia para dejar el pago registrado como pendiente en el Dashboard.`,

  appointments_small: (name, currency) => `Eres el asistente oficial de citas y servicios de ${name}.
OBJETIVO PRINCIPAL:
- Orientar al cliente sobre los servicios disponibles, informar tarifas en ${currency} y agendar citas automáticamente.
FLUJO AUTOMÁTICO DE CITAS:
1. Informa qué servicios ofrecemos y sus tarifas según el catálogo activo.
2. Para agendar una cita, solicita: Nombre y apellido, Teléfono, Servicio deseado y Fecha/Hora preferida.
3. Registra la solicitud de cita en el Dashboard para confirmación del negocio.`,

  restaurant: (name, currency) => `Eres el anfitrión y tomador de pedidos automatizado de ${name} (Restaurante / Cafetería).
OBJETIVO PRINCIPAL:
- Mostrar el menú activo, preparar pedidos de comida o registrar reservas de mesa automáticamente en el Dashboard.
FLUJO AUTOMÁTICO:
1. Si el cliente desea RESERVAR MESA: solicita Nombre completo, Teléfono, Cantidad de personas y Fecha/Hora.
2. Si el cliente desea PEDIR COMIDA: confirma los platos del menú, calcula el total en ${currency}, muestra los métodos de pago y registra la referencia.`
};

function generateBusinessAiPrompt(onlyIfEmpty = false) {
  const textarea = document.getElementById('business_needs');
  const helper = document.getElementById('ai-prompt-helper');
  if (!textarea) return;
  if (onlyIfEmpty && textarea.value.trim()) return;
  const businessName = (document.getElementById('business_name')?.value || '').trim() || (selectedProfile ? selectedProfile.label : 'nuestro negocio');
  const currency = (document.getElementById('currency')?.value || 'USD').trim();
  const typeCode = selectedBusinessType || 'tech_store';
  const builder = BUSINESS_AI_PROMPTS[typeCode] || BUSINESS_AI_PROMPTS.tech_store;
  textarea.value = builder(businessName, currency);
  textarea.style.borderColor = '#00f2fe';
  textarea.style.boxShadow = '0 0 0 3px rgba(0, 242, 254, 0.18)';
  setTimeout(() => {
    textarea.style.borderColor = '';
    textarea.style.boxShadow = '';
  }, 1400);
  if (helper) {
    helper.innerHTML = `<span style="color:#38f9d7;font-weight:600;">✓ Prompt generado para ${escapeHtml(selectedProfile ? selectedProfile.label : typeCode)}.</span> Puedes ajustarlo cuando quieras desde el Dashboard.`;
  }
}

function renderSelectedPlanStrip() {
  const strip = document.getElementById('selected-plan-strip');
  if (!strip || !selectedProfile || !selectedPlan) return;
  const priceText = Number(selectedPlan.price_usd) === 0 ? 'GRATIS ($0)' : `$${Number(selectedPlan.price_usd).toFixed(0)}`;
  strip.innerHTML = `<div class="strip-icon">✦</div><div><strong>${escapeHtml(selectedProfile.label)}</strong><small>${escapeHtml(selectedPlan.label)} · ${escapeHtml(selectedProfile.dashboard_label || 'Panel Ejecutivo')}</small></div><div class="strip-price"><strong>${priceText}</strong><small>USD/mes</small></div>`;
  const context = document.getElementById('checkout-context');
  if (context) {
    if (checkoutJourneyLocked && checkoutRef) {
      const method = PAYMENT_LABELS[checkoutMethod] || checkoutMethod || 'Verificado';
      context.hidden = false;
      context.innerHTML = `Referencia PRO: <strong>${escapeHtml(checkoutRef)}</strong> · Método: <strong>${escapeHtml(method)}</strong> · <span id="checkout-payment-status" style="color:#38f9d7;font-weight:700">Pago aprobado ✓</span>`;
    } else {
      context.hidden = false;
      context.innerHTML = `Modalidad seleccionada: <strong>Plan Free ($0/mes)</strong> · Activación directa inmediata sin pago previo.`;
    }
  }
}

function readRequest() {
  const name = document.getElementById('business_name').value.trim();
  const owner = document.getElementById('owner_full_name').value.trim();
  const phone = document.getElementById('owner_phone').value.trim();
  const email = document.getElementById('owner_email').value.trim().toLowerCase();
  const password = document.getElementById('owner_password').value;
  const passwordConfirm = document.getElementById('owner_password_confirm').value;
  if (!selectedProfile || !selectedPlan) throw new Error('Selecciona primero la actividad de tu negocio.');
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
  const priceLabel = Number(selectedPlan.price_usd) === 0 ? '$0' : `$${Number(selectedPlan.price_usd).toFixed(0)}`;
  summary.innerHTML = `
    <div class="summary-plan"><div><span class="summary-eyebrow">CUENTA LISTA PARA ACTIVAR</span><h2>${escapeHtml(request.businessName)}</h2><p>${escapeHtml(selectedProfile.label)} · ${escapeHtml(selectedPlan.label)}</p></div><div class="summary-amount"><strong>${priceLabel}</strong><small>USD / mes</small></div></div>
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
        checkout_ref: checkoutRef || null,
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
    const rawBody = await response.text().catch(() => '');
    let data = {};
    try { data = rawBody ? JSON.parse(rawBody) : {}; } catch (_) { data = {}; }
    if (!response.ok) {
      let errMsg = 'No se pudo completar la creación del negocio.';
      if (typeof data.detail === 'string' && data.detail.trim()) {
        errMsg = data.detail.trim();
      } else if (Array.isArray(data.detail) && data.detail.length) {
        errMsg = data.detail.map(item => item.msg || JSON.stringify(item)).join(' · ');
      } else if (typeof data.message === 'string' && data.message.trim()) {
        errMsg = data.message.trim();
      } else if (rawBody && rawBody.length < 240 && !rawBody.trim().startsWith('<')) {
        errMsg = `No se pudo completar la creación del negocio (${rawBody.trim()}).`;
      }
      throw new Error(errMsg);
    }
    if (data.access_token) {
      localStorage.setItem('galaxy_access_token', data.access_token);
      localStorage.setItem('galaxy_role', 'OWNER');
      if (data.business_id) {
        localStorage.setItem('galaxy_business_id', String(data.business_id));
      }
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

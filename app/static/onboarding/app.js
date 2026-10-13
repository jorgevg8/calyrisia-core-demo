// Muestras de 10 productos por industria
const INDUSTRY_PRODUCTS = {
    restaurante: `Hamburguesa Especial Calyrisia - 8.50
Hamburguesa Doble Queso y Tocineta - 11.00
Perro Caliente Gigante con Todo - 4.00
Papas Fritas Rústicas con Queso - 3.50
Nuggets de Pollo Crujientes (8 pcs) - 5.00
Pizza Personal Pepperoni - 7.00
Tequeños con Salsa Tártara (6 pcs) - 4.50
Refresco Frío 355ml - 1.50
Malteada Cremosa de Chocolate - 3.50
Postre Brownie con Helado - 4.00`,

    textil: `Camisa de Lino Manga Larga - 25.00
Pantalón Jean Slim Fit Clásico - 32.00
Vestido Casual Elegante - 28.00
Blusa de Seda Estampada - 22.00
Chaqueta Denim Clásica - 45.00
Short Playero Casual - 16.00
Franela Básica 100% Algodón - 12.00
Zapatos Casuales de Cuero - 48.00
Cinturón de Cuero Reversible - 15.00
Lentes de Sol Polarizados - 18.00`,

    supermercado: `Harina de Maíz PAN 1kg - 1.30
Arroz Blanco Premium 1kg - 1.20
Aceite Vegetal 1 Litro - 2.80
Queso Blanco Llanero 1kg - 5.50
Café Molido Gourmet 500g - 4.20
Pasta Larga Espagueti 1kg - 1.50
Leche Líquida Completa 1L - 1.80
Nutella Crema Avellanas 350g - 5.50
Refresco Familiar 2 Litros - 2.50
Pack 4 Rollos Papel Higiénico - 2.00`,

    clinica: `Consulta Médica General - 25.00
Consulta Odontológica y Limpieza - 35.00
Perfil 20 Exámenes de Sangre - 20.00
Ecosonograma Abdominal - 30.00
Electrocardiograma con Informe - 22.00
Control Pediátrico Integral - 28.00
Tratamiento de Conducto - 60.00
Extracción Dental Simple - 20.00
Prueba Rápida de Laboratorio - 10.00
Certificado Médico Vial - 15.00`,

    servicios: `Cable de Carga Rápida USB-C - 6.00
Cargador de Pared 20W - 12.00
Auriculares Inalámbricos Bluetooth - 22.00
Soporte Magnético para Teléfono - 8.50
Powerbank Portátil 10000mAh - 18.00
Protector de Pantalla Vidrio 9D - 5.00
Funda Protectora Antigolpes - 7.50
Memoria MicroSD 64GB Clase 10 - 9.00
Mouse Inalámbrico Ergonómico - 11.50
Teclado Mecánico RGB - 35.00`
};

function loadSampleProducts() {
    const bType = document.getElementById('business_type').value || 'restaurante';
    const productsEl = document.getElementById('products_list');
    if (productsEl && (!productsEl.value.trim() || confirm('¿Deseas reemplazar el catálogo actual por los 10 productos sugeridos?'))) {
        productsEl.value = INDUSTRY_PRODUCTS[bType] || INDUSTRY_PRODUCTS.restaurante;
    }
}

// Navegación entre pasos
function nextStep(stepNumber) {
    if (stepNumber === 2) {
        // Al entrar al paso 2, precargar los 10 productos si está vacío
        const bType = document.getElementById('business_type').value || 'restaurante';
        const productsEl = document.getElementById('products_list');
        if (productsEl && !productsEl.value.trim()) {
            productsEl.value = INDUSTRY_PRODUCTS[bType] || INDUSTRY_PRODUCTS.restaurante;
        }
    }

    document.querySelectorAll('.step').forEach(step => step.classList.add('hidden'));
    document.querySelectorAll('.step').forEach(step => step.classList.remove('active'));
    
    const nextEl = document.getElementById(`step-${stepNumber}`);
    if (nextEl) {
        nextEl.classList.remove('hidden');
        nextEl.classList.add('active');
    }
}

function prevStep(stepNumber) {
    nextStep(stepNumber);
}

// Envío al backend
async function submitOnboarding() {
    const aiPromptInput = document.getElementById('ai_prompt');
    const productsInput = document.getElementById('products_list');

    const payload = {
        business_type: document.getElementById('business_type').value || 'restaurante',
        business_name: document.getElementById('business_name').value,
        ai_prompt: aiPromptInput ? aiPromptInput.value.trim() : "",
        products_text: productsInput ? productsInput.value.trim() : "",
        currency: document.getElementById('currency').value || 'USD',
        owner_full_name: document.getElementById('owner_full_name').value,
        owner_email: document.getElementById('owner_email').value,
        owner_phone: document.getElementById('owner_phone').value,
        owner_password: document.getElementById('owner_password').value
    };

    const launchBtn = document.querySelector('.btn-launch');
    if (launchBtn) {
        launchBtn.disabled = true;
        launchBtn.innerText = "Provisionando IA y Catálogo...";
    }

    try {
        const response = await fetch('/api/v1/onboarding/business', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            localStorage.setItem("calyrisia_current_business_id", data.business_id);
            localStorage.setItem("calyrisia_current_business_name", payload.business_name);
            localStorage.setItem("calyrisia_current_business_type", payload.business_type);
            
            // Iniciar sesión automáticamente en este negocio para el Dashboard
            if (data.access_token) {
                localStorage.setItem("galaxy_access_token", data.access_token);
                localStorage.setItem("galaxy_role", "OWNER");
            }

            // Limpiar chats anteriores para evitar mezclas entre negocios
            localStorage.removeItem("galaxy_webchat_customer_id");
            localStorage.removeItem("galaxy_webchat_conversation_id");

            document.getElementById('final_business_id').innerText = data.business_id;
            nextStep(4);
        } else {
            alert("Error en el registro: " + (data.detail || JSON.stringify(data)));
            if (launchBtn) {
                launchBtn.disabled = false;
                launchBtn.innerText = "Lanzar Sistema 🚀";
            }
        }
    } catch (error) {
        console.error("Error de red:", error);
        alert("Ocurrió un error al conectar con el servidor.");
        if (launchBtn) {
            launchBtn.disabled = false;
            launchBtn.innerText = "Lanzar Sistema 🚀";
        }
    }
}

function goToDashboard() {
    window.location.href = '/dashboard/';
}

function goToWebchat() {
    const bizId = localStorage.getItem("calyrisia_current_business_id");
    if (bizId) {
        window.location.href = `/webchat?business_id=${encodeURIComponent(bizId)}`;
    } else {
        window.location.href = '/webchat';
    }
}

function goToFeedback() {
    window.location.href = '/feedback';
}

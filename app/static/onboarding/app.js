// Navegación entre pasos
function nextStep(stepNumber) {
    document.querySelectorAll('.step').forEach(step => step.classList.add('hidden'));
    document.querySelectorAll('.step').forEach(step => step.classList.remove('active'));
    
    const nextEl = document.getElementById(`step-${stepNumber}`);
    nextEl.classList.remove('hidden');
    nextEl.classList.add('active');
}

function prevStep(stepNumber) {
    nextStep(stepNumber);
}

// Envío atómico al backend
async function submitOnboarding() {
    const payload = {
        business_type: document.getElementById('business_type').value,
        business_name: document.getElementById('business_name').value,
        currency: document.getElementById('currency').value,
        owner_full_name: document.getElementById('owner_full_name').value,
        owner_email: document.getElementById('owner_email').value,
        owner_phone: document.getElementById('owner_phone').value,
        owner_password: document.getElementById('owner_password').value
    };

    // Nota: ai_prompt y timezone se pueden enviar aquí si los agregas al modelo Pydantic luego, 
    // pero por ahora FastAPI procesará el negocio y el owner perfectamente con estos.

    try {
        const response = await fetch('/api/v1/onboarding/business', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Mostrar ID final y pasar al paso 4
            document.getElementById('final_business_id').innerText = data.business_id;
            nextStep(4);
        } else {
            alert("Error en el registro: " + (data.detail || JSON.stringify(data)));
        }
    } catch (error) {
        console.error("Error de red:", error);
        alert("Ocurrió un error al conectar con el servidor.");
    }
}

function goToDashboard() {
    window.location.href = '/dashboard/';
}
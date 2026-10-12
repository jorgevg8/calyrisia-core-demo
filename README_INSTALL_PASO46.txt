GALAXY PASO 46 — PATCH

Este ZIP es un PATCH para tu Core actual después del Paso 45.
No reemplaza el proyecto completo. Extrae su contenido sobre:
C:\Proyecto Galaxy\galaxy_core_v1

Incluye:
- Approval & Human Operations Center V2
- cola unificada de approvals + handoffs
- aprobar/rechazar/reintentar approvals
- expiración
- auditoría de decisiones
- reanudación de workflows aprobados
- acknowledge/resolve de handoffs
- /operations/ UI

Antes de extraer:
1) detener Uvicorn
2) hacer backup del core actual

Después:
1) iniciar Galaxy con INICIAR_GALAXY.bat
2) ejecutar scripts\paso46_setup_operations_center.py
3) ejecutar scripts\paso46_operations_center_test.py
4) abrir http://127.0.0.1:8000/operations/

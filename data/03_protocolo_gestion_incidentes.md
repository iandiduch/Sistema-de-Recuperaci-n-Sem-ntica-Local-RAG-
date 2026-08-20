# Protocolo Operativo de Gestión, Mitigación y Escalado de Incidentes Críticos

## 1. Clasificación de Niveles de Severidad (SEV)

Para priorizar los esfuerzos del equipo de ingeniería y operaciones durante interrupciones en producción, se define la siguiente matriz de severidad:

- **SEV-1 (Catastrófico / Bloqueo Total)**:
  - Impacto: Caída total del sistema de pagos, indisponibilidad del servicio principal que afecta a más del 25% de los usuarios activos, o brecha de seguridad con compromiso de datos confidenciales.
  - Tiempo Objetivo de Respuesta Inicial (TTRA): Menor a **5 minutos** (24/7/365).
  - Tiempo Objetivo de Mitigación (MTTR): Menor a **30 minutos**.
- **SEV-2 (Crítico / Degradación Severa)**:
  - Impacto: Falla en funciones clave del negocio sin solución alternativa viable (ej. generación de facturas o procesamiento asíncrono de pedidos con retraso acumulado mayor a 1 hora).
  - Tiempo Objetivo de Respuesta Inicial: Menor a **15 minutos**.
  - Tiempo Objetivo de Mitigación: Menor a **2 horas**.
- **SEV-3 (Moderado / Impacto Menor)**:
  - Impacto: Errores en reportes no críticos, fallas en la interfaz de administración interna o lentitud intermitente que afecta a menos del 5% de las solicitudes.
  - Tiempo Objetivo de Respuesta: Menor a **2 horas hábiles**.
- **SEV-4 (Bajo / Mejora Operativa)**:
  - Impacto: Problemas cosméticos de UI o discrepancias menores en logs. Tratado en el backlog ordinario de sprint.

## 2. Roles y Cadena de Mando durante Incidentes SEV-1 y SEV-2

Durante la activación de un incidente SEV-1 o SEV-2 en PagerDuty, se establece de inmediato una sala de crisis (*War Room*) en Slack y Google Meet con los siguientes roles designados:

1. **Comandante del Incidente (Incident Commander - IC)**:
   - Es la máxima autoridad operativa durante la emergencia.
   - No escribe código ni realiza diagnósticos técnicos directamente; coordina a los equipos, asigna tareas de investigación y autoriza cambios en caliente o rollbacks.
2. **Líder Técnico (Tech Lead - TL)**:
   - Dirige la investigación técnica de causa raíz, analiza métricas en Datadog/Grafana y coordina los despliegues de parches o reversiones de versión (*Canary Rollbacks*).
3. **Oficial de Comunicaciones (Communications Lead - CL)**:
   - Publica actualizaciones cada 15 minutos en la página de estado pública (`status.empresa.com`) y mantiene informados a los líderes de producto y soporte al cliente.

## 3. Filosofía de Postmortem sin Culpas (*Blameless Post-Mortem*)

Dentro de las **48 horas posteriores** a la mitigación definitiva de cualquier incidente SEV-1 o SEV-2, el Comandante del Incidente debe organizar y liderar una sesión de autopsia blameless.
- El objetivo exclusivo es identificar fallas sistémicas en la arquitectura, brechas de observabilidad y mejoras en los procesos de despliegue continuo (CI/CD).
- Se prohíbe señalar culpabilidades individuales.
- Todo postmortem debe generar un informe estructurado con una cronología exacta y al menos 3 ítems de acción con responsables asignados y fecha de entrega.

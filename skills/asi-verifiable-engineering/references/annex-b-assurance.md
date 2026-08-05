# Anexo B — Modelo de aseguramiento progresivo T0–T6

## Regla institucional

La confianza no pertenece a una IA ni a una conversación. Pertenece temporalmente a un commit específico, ejecutado en un entorno identificado, bajo controles independientes y dentro de un alcance explícito.

## B.1 Niveles de aseguramiento

### T0 — Propuesta no verificada

La IA generó o modificó código, pero no existe evidencia suficiente de ejecución.

- Uso permitido: análisis, experimento aislado y revisión.
- Uso prohibido: integración, publicación o despliegue.

### T1 — Estructuralmente válido

El cambio tiene diff identificable, respeta alcance, pasa validaciones estructurales y no presenta cambios accidentales evidentes. T1 no demuestra corrección funcional.

### T2 — Funcionalmente probado

Compila, pasa pruebas relevantes, incorpora pruebas cuando cambia comportamiento, pasa controles estáticos y básicos de seguridad y no introduce regresiones detectadas. Solo demuestra casos evaluados.

### T3 — Verificado independientemente

Una entidad distinta al constructor revisa diff, prueba que las pruebas puedan fallar, intenta invalidar hipótesis, confirma comandos y evalúa riesgos e incertidumbres.

### T4 — Reproducible y protegido

Puede reproducirse desde entorno limpio, pasa CI, queda protegido por puertas obligatorias, no puede integrarse cuando fallan y conserva evidencia trazable.

### T5 — Observado en operación

El despliegue controlado demuestra comportamiento esperado sin degradación material, corrupción o ruptura de integraciones y con capacidad de reversión.

### T6 — Resiliente

Se prueban, cuando aplican, fallos parciales, pérdida de red, timeouts, reintentos, duplicación, concurrencia, recuperación, restauración, degradación y rollback.

Las rutas que manejan dinero, permisos, secretos, datos sensibles o disponibilidad crítica no se consideran confiables solo por T2 o T3.

## B.2 Funciones separadas

- **Constructor:** analiza, propone, programa, prueba y declara riesgos; no aprueba definitivamente.
- **Auditor:** comienza en solo lectura, revisa diff, honestidad de pruebas, seguridad, arquitectura y omisiones.
- **CI:** autoridad mecánica para build, pruebas, estático, cobertura, seguridad, dependencias, reproducibilidad e integración.
- **Aprobador:** puede ser automático únicamente en riesgo bajo bajo política explícita; alto y crítico requieren humano.

## B.3 Evidencia producida por herramientas

“Toda prueba pasó” es una interpretación, no una evidencia primaria. Adjuntar commit, diff, comandos, códigos, logs, informes, cobertura, análisis estático, seguridad, CI, entorno, fecha, duración y controles omitidos.

## B.4 Honestidad de las pruebas

Una suite verde no demuestra capacidad de detección. Aplicar por riesgo:

- mutation testing;
- pruebas negativas;
- property-based testing;
- fuzzing;
- límites;
- contratos;
- inyección controlada de fallos;
- retirada temporal de la corrección.

Una prueba que sigue pasando al eliminar la corrección no protege el comportamiento.

## B.5 Prohibición de manipular controles

Antes de modificar una prueba fallida explicar causa, ubicación del defecto, comportamiento esperado y evidencia que justifica la modificación.

Prohibido eliminar pruebas para aprobar, debilitar aserciones, inflar timeouts, crear excepciones globales, ignorar warnings críticos, excluir cobertura, reintentar hasta verde, desactivar escáneres o silenciar códigos.

Todo cambio de CI, pruebas, lint, cobertura o seguridad recibe revisión superior al código ordinario.

## B.6 Confianza proporcional al riesgo

La matriz vinculante está en [Anexo C](annex-c-control-matrix.md).

- Bajo: T4, revisión automática independiente y muestreo humano.
- Medio: T4, auditor independiente, integración, rollback y observación posterior.
- Alto: revisión humana especializada, doble verificación, pruebas adversariales, despliegue gradual, monitoreo y rollback inmediato.
- Crítico: aprobación humana explícita, separación estricta, ensayo, recuperación, despliegue limitado y prohibición de autonomía total.

## B.7 Verificación posterior al despliegue

Usar feature flags, canary, porcentaje limitado, shadow traffic, staging representativo, comparación de resultados, monitoreo reforzado o rollback automático según riesgo.

Comparar errores, latencia, recursos, integridad de datos, resultados, dependencias y eventos de seguridad. Un cambio que falla en operación pierde nivel de confianza.

## B.8 Caducidad

La confianza solo vale para commit, dependencias, entorno, configuración, artefactos y periodo evaluados. Reevaluar ante cambios de código, dependencia, runtime, sistema operativo, infraestructura, configuración, secretos, API externa, amenaza conocida o condiciones de producción.

## B.9 Muestreo humano

Incluso con aprobación automática de bajo riesgo, revisar periódicamente muestras para detectar fallos sistemáticos, pruebas engañosas, deuda, sobreingeniería, pérdida de claridad, inseguridad, desviación arquitectónica y manipulación de métricas.

La autonomía se gana con evidencia histórica y se pierde con fallos.

## B.10 Historial del agente

Registrar cambios producidos, defectos detectados antes de integrar, defectos escapados, regresiones, vulnerabilidades, retrabajo, precisión de declaraciones, no verificado, cumplimiento de alcance y rollback.

La reputación general del modelo no sustituye el historial observado en el contexto real.

## B.11 Omisión de revisión línea por línea

Solo para riesgo bajo o medio controlado, diff pequeño y coherente, auditor independiente, CI obligatorio e inalterable por el constructor, pruebas honestas, ausencia de secretos/permisos nuevos/migraciones irreversibles, controles no modificados, rollback, ausencia de incertidumbre relevante, historial aceptable y observación posterior.

Si falta una condición, escalar.

## B.12 Pregunta institucional

No preguntar únicamente “¿podemos confiar en esta IA?”. Preguntar:

> ¿Qué daño puede causar este cambio, qué evidencia demuestra que funciona, qué quedó sin verificar y qué mecanismos permiten detectarlo y revertirlo si falla?

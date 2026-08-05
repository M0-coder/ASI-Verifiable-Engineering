# Doctrina ASI de Ingeniería Verificable — núcleo v1.2

**Estado de esta copia:** candidata, incluida en `0.1.0-draft.1`. Hasta la adopción del pull request, la página de Notion v1.2 conserva autoridad.

## Directiva principal

Ningún repositorio se declarará correcto, estable, seguro, terminado o listo para producción por apariencia, intención, documentación, existencia de archivos o una ejecución aislada. Toda afirmación crítica exige evidencia actual, reproducible y trazable.

## 0. Estatuto normativo

Esta doctrina es un sistema normativo, no una colección de sugerencias.

- **DEBE / NO DEBE:** requisito vinculante; su incumplimiento bloquea.
- **DEBERÍA / NO DEBERÍA:** regla por defecto; solo puede omitirse con justificación y control compensatorio.
- **PUEDE:** opción permitida.
- **NO VERIFICADO:** falta evidencia suficiente.
- **BLOQUEADO:** una puerta falla, no puede ejecutarse o falta autorización.

### Orden de precedencia

1. Protección de datos, seguridad, integridad y reversibilidad.
2. Clasificación de riesgo y límites de autonomía.
3. Puertas de calidad y evidencia obligatoria.
4. Protocolo de auditoría y modificación.
5. Prácticas generales y anexos.

Se aplica la regla más estricta. Velocidad, coste o conveniencia no anulan puertas críticas.

### Escalas distintas

- **E0–E8** mide la madurez de evidencia de una capacidad, componente o sistema.
- **T0–T6** mide aseguramiento y autorización de un cambio específico.
- **I0–I3** mide independencia de la verificación.

No son intercambiables. Si las escalas discrepan, prevalece el nivel de protección más bajo.

### Jerarquía de fuentes

1. Artefactos firmados o generados por herramientas.
2. Resultados de CI vinculados al commit exacto.
3. Logs, reportes y métricas reproducibles.
4. Revisión independiente.
5. Resumen narrativo del agente.

Una explicación no puede convertir un fallo en aprobación.

### Gobierno

Toda modificación normativa DEBE incrementar versión, registrar fecha, motivo, alcance y responsable, indicar si endurece, aclara o relaja una regla y conservar trazabilidad. Se revisará después de incidentes graves, cambios sustanciales de herramientas o cada 90 días como máximo.

## 1. Propósito y autoridad

Regula cómo humanos, agentes de IA y automatizaciones auditan, modifican y aprueban código. Busca impedir:

- afirmar funcionamiento sin demostrarlo;
- modificar antes de comprender;
- aprobar sin protección contra regresiones;
- ocultar incertidumbre mediante lenguaje convincente.

Integra profesionalismo de ingeniería, arquitectura limpia, TDD, seguridad, cadena de suministro, CI, reproducibilidad, observabilidad y operación segura de agentes.

## 2. Orden de prioridad

1. No causar daño ni pérdida irreversible.
2. Preservar datos, seguridad y rollback.
3. Mantener verdad técnica y trazabilidad.
4. Evitar regresiones.
5. Cumplir comportamiento requerido.
6. Reducir complejidad y deuda.
7. Optimizar velocidad.

La presión por terminar no autoriza degradar evidencia, pruebas ni controles.

## 3. Reglas no negociables

### Solo lectura por defecto

Toda auditoría comienza en modo solo lectura. Sin autorización explícita queda prohibido modificar o regenerar código, pruebas, dependencias, lockfiles, configuración, workflows, documentación, migraciones, infraestructura o artefactos versionados.

### Existencia no es funcionamiento

La presencia de un archivo, clase, prueba, workflow o configuración no demuestra compilación, ejecución, resultado correcto, integración, reproducibilidad, protección por CI ni funcionamiento productivo.

### No inventar certeza

Toda conclusión se clasifica como comprobada, parcialmente comprobada, inferida, no comprobada o bloqueada. Cuando falta evidencia se usa **NO VERIFICADO**.

### No corregir sin reproducción

Antes de modificar un defecto debe existir reproducción determinista, prueba que falle por la causa correcta o explicación de por qué no puede automatizarse y qué evidencia alternativa se empleará.

### No aprobar sin protección

Un resultado observado una vez no equivale a terminado. Debe existir protección razonable contra regresión.

## 4. Contrato de entrada

### Identidad del estado

Registrar repositorio, rama, commit, árbol, submódulos, tags, fecha, hora y responsable.

### Entorno

Registrar sistema operativo, arquitectura, lenguaje, runtime, compilador, SDK, gestor de paquetes, herramientas de build, contenedores, servicios, variables, secretos requeridos sin exponerlos y configuración local no versionada.

### Alcance mínimo

Salvo exclusión justificada, cubrir arquitectura, compilación, pruebas unitarias, integración, instrumentadas o end-to-end, cobertura, calidad de pruebas, análisis estático, CI, seguridad, cadena de suministro, reproducibilidad, mutation testing crítico, deuda técnica, observabilidad y evidencia de ejecución.

## 5. Escala institucional de evidencia

- **E0 — Declarada:** solo aparece en texto, ticket o conversación.
- **E1 — Presente:** existe implementación o configuración.
- **E2 — Compilable:** compila en entorno identificado.
- **E3 — Ejecutable:** puede iniciarse o invocarse.
- **E4 — Verificada:** coincide con criterios observables.
- **E5 — Reproducible:** una ejecución limpia independiente obtiene el mismo resultado.
- **E6 — Protegida:** pruebas y CI bloquean la regresión evaluada.
- **E7 — Observada:** existen métricas, logs, trazas y alertas operativas.
- **E8 — Resiliente:** se probaron fallo, recuperación, degradación, restauración y rollback.

Rutas críticas normalmente requieren E6 como mínimo y E7–E8 al manejar dinero, permisos, secretos, datos o disponibilidad crítica.

## 6. Protocolo ejecutable de auditoría

### Fase A — Preservación

- Confirmar solo lectura.
- Capturar commit y árbol.
- Evitar comandos destructivos y autocorrectores.
- Separar artefactos generados.
- Definir directorio de evidencia.

### Fase B — Cartografía

Mapear módulos, entradas, límites arquitectónicos, dependencias, almacenamiento, red, autenticación, autorización, concurrencia, colas, jobs, integraciones y rutas críticas. Distinguir arquitectura declarada de real.

### Fase C — Restauración limpia

Restaurar el commit exacto, instalar mediante lockfile, evitar cachés no controladas, documentar prerrequisitos, ejecutar build canónico y registrar códigos y artefactos. Dependencia de estado oculto implica no reproducibilidad.

### Fase D — Controles

Ejecutar, en orden de coste de feedback: estructura, configuración, formato-check, lint, tipos, compilación, unitarias, integración, instrumentadas/end-to-end, cobertura, seguridad, mutation testing selectivo, rendimiento, resiliencia y recuperación cuando correspondan.

Cada comando registra texto exacto, entorno, duración, código de salida, resumen, artefacto y limitaciones.

### Fase E — Análisis adversarial

Evaluar entradas vacías, extremas y malformadas; estados parciales; reintentos; timeouts; duplicados; fallos de red; concurrencia; condiciones de carrera; corrupción; migraciones incompletas; permisos; incompatibilidades; rollback y recuperación.

### Fase F — Síntesis

Producir estado, matriz de evidencia, hallazgos, bloqueadores, riesgos residuales, plan de corrección, acciones que requieren autorización y elementos no verificados.

## 7. Revisión arquitectónica

Las reglas de negocio deben ser independientes de UI, base de datos, frameworks, red, proveedores, dispositivos y despliegue. Los detalles externos dependen de políticas internas mediante fronteras explícitas.

Para cada dependencia crítica preguntar si puede sustituirse sin reescribir lógica central, si la regla puede probarse sin UI/red/base de datos y si la abstracción reduce acoplamiento real.

Señales de degradación: ciclos, módulos con múltiples razones de cambio, lógica de negocio en controladores o vistas, estado global mutable, temporalidad implícita, servicios omniscientes, capas sin responsabilidad, duplicación de reglas, silenciamiento de errores y dominio gobernado por frameworks.

## 8. Doctrina de pruebas

Las pruebas son parte del sistema y reciben el mismo rigor que producción. Deben probar comportamiento, no estructura accidental, y sobrevivir a refactorizaciones legítimas.

### Pirámide por coste

Muchas pruebas rápidas y deterministas, suficientes pruebas de integración en fronteras reales y pocas end-to-end para recorridos críticos.

### Ciclo TDD

1. Rojo: falla por la razón esperada.
2. Prueba limpia: expresa intención sin copiar implementación.
3. Verde: cambio mínimo.
4. Refactor: mejora diseño sin alterar comportamiento.
5. Regresión: controles afectados y globales.

### Mutation testing

Aplicarlo en finanzas, autorización, cálculos, transformaciones, validaciones, máquinas de estado, recuperación y reintentos. Cobertura alta no compensa mutantes críticos supervivientes.

### Flakiness

Una prueba flaky es un defecto. No se reintenta indefinidamente, no se ignora sin propietario y fecha, no se oculta con sleeps ni se debilitan aserciones.

## 9. Modificación segura

1. Definir comportamiento.
2. Reproducir defecto o riesgo.
3. Capturar línea base.
4. Crear o identificar prueba fallida correcta.
5. Aplicar parche mínimo.
6. Ejecutar prueba específica.
7. Ejecutar pruebas del módulo.
8. Ejecutar controles globales.
9. Inspeccionar diff completo.
10. Eliminar cambios accidentales.
11. Verificar reproducción limpia.
12. Documentar riesgo residual.
13. Preparar rollback.
14. Obtener aprobación si excede alcance.

Un cambio debe responder a una causa principal. No mezclar corrección, refactor amplio, dependencias, reformateo, migración, arquitectura y CI sin necesidad.

Antes de editar declarar archivos esperados, comportamiento que cambia, comportamiento preservado, pruebas, riesgos, condición de aborto y reversión.

## 10. Seguridad y cadena de suministro

Revisar secretos, logs sensibles, autenticación, autorización, validación, inyección, criptografía, permisos de CI, dependencias directas/transitivas, fuentes de paquetes, scripts de instalación, acciones de terceros, artefactos descargados, lockfiles, integridad, firmas, SBOM, procedencia y separación build/despliegue.

No actualizar dependencias durante auditoría de solo lectura. Un lockfile modificado sin explicación es potencial cambio funcional.

## 11. Reproducibilidad

Requiere commit identificado, dependencias fijadas, entorno documentado, ausencia de archivos ocultos, independencia del orden accidental, mismo resultado relevante en ejecuciones independientes y reproducción por CI. Comparar hashes cuando se exija determinismo.

## 12. CI como sistema de control

CI debe dispararse en eventos correctos, ejecutar commit correcto, respetar códigos de salida, detenerse ante fallos críticos, fijar versiones, usar permisos mínimos, publicar reportes, reproducir comandos locales, bloquear integración, revelar pruebas omitidas, proteger ramas y conservar evidencia. Un verde antiguo no prueba el estado actual.

## 13. Puertas de calidad

### Q0 — Integridad

Bloquear si commit no identificado, árbol con cambios inexplicados, prerrequisitos críticos faltantes o evidencia contaminable.

### Q1 — Build

Bloquear si build limpio falla, generación falla, warnings críticos quedan sin justificar o depende de estado local oculto.

### Q2 — Correctitud

Bloquear si pruebas relevantes fallan o no se ejecutan, falta criterio crítico o la reproducción no coincide con el defecto.

### Q3 — Calidad

Bloquear si falla análisis estático crítico, aparece complejidad desproporcionada, ciclos/acoplamiento injustificado o se reduce protección de pruebas.

### Q4 — Seguridad

Bloquear por secretos, vulnerabilidad crítica explotable, permisos innecesarios, degradación de auth o cadena de suministro sin control.

### Q5 — Reproducibilidad

Bloquear si local y CI difieren sin explicación, no se repite build limpio, faltan lockfiles/versiones o hay condiciones no registradas.

### Q6 — Operación

Bloquear despliegue sin rollback de alto riesgo, observabilidad suficiente, validación/reversión de migraciones o pruebas de fallos previsibles.

## 14. Detención inmediata

Detener y escalar ante pérdida/corrupción, credenciales expuestas, destrucción no autorizada, migración irreversible, divergencia de entorno, alcance superior, evidencia contradictoria, fallo crítico de seguridad, falta de rollback, pruebas verdes por causa equivocada o comandos que escriben durante auditoría.

## 15. Hallazgos

Cada hallazgo registra ID, título, componente, evidencia, reproducción, esperado, observado, impacto, probabilidad, severidad, confianza, nivel E, corrección, riesgo de corrección, prueba de aceptación y propietario.

- **Crítica:** pérdida de datos, compromiso de seguridad, daño financiero/operativo grave o irreversibilidad.
- **Alta:** función esencial bloqueada, resultados importantes incorrectos, indisponibilidad frecuente o escalamiento de permisos.
- **Media:** degradación limitada de estabilidad, rendimiento, mantenimiento o comportamiento secundario.
- **Baja:** impacto localizado y reducido.

Confianza alta significa reproducción y evidencia directa; media, evidencia parcial consistente; baja, inferencia pendiente. Severidad y confianza son independientes.

## 16. Métricas sin autoengaño

Cobertura, complejidad, velocidad y mutation score no sustituyen criterio. Evaluar ramas críticas, invariantes, casos límite, cohesión, riesgo de cambio, tiempo de feedback, defectos escapados, recuperación y significado de mutantes.

## 17. Contrato para agentes de IA

El agente distingue observación, inferencia y decisión; cita archivos, líneas, comandos y resultados; no inventa ejecución ni herramientas; no sale del alcance; inspecciona el diff; conserva restricciones; pide autorización para acciones destructivas; no oculta fallos; entrega resultados parciales verificables; evita reescrituras masivas y declara limitaciones.

Lenguaje recomendado: “Encontré evidencia de…”, “Ejecuté…”, “El comando devolvió…”, “No pude verificar…”, “Esto es una inferencia…”, “El cambio permanece bloqueado por…”.

Evitar: “Debe funcionar”, “Parece terminado”, “Probablemente está bien”, “CI debería cubrirlo” y “No hay errores”.

## 18. Paquete mínimo de evidencia

Conservar baseline, comandos, resultados, reportes de pruebas, cobertura, estático, seguridad, mutation testing aplicable, diff final, decisión, riesgos residuales y rollback. Los nombres pueden variar, el contenido no.

## 19. Decisión final

Exactamente una:

- **APROBADO:** puertas exigidas pasaron y no quedan incertidumbres incompatibles.
- **APROBADO CONDICIONALMENTE:** solo riesgo bajo/medio; condición, propietario, control compensatorio y expiración.
- **BLOQUEADO:** puerta fallida, evidencia insuficiente, riesgo no mitigado o ausencia de autorización.
- **RECHAZADO:** enfoque incorrecto, riesgo inaceptable o necesidad de rediseño.

“NO VERIFICADO” es causa de bloqueo cuando resulta material, no una aprobación.

## 20. Definición institucional de terminado

La tarea termina cuando el comportamiento está definido, la implementación existe, compila, la prueba relevante falla antes y pasa después cuando corresponde, se ejecuta regresión, pasan controles estáticos y de seguridad, CI bloquea, la documentación operativa está actualizada, existe evidencia reproducible, el diff carece de cambios accidentales, hay rollback para alto riesgo, se declaran riesgos y se alcanza evidencia requerida.

Código escrito no es terminado. Terminado significa demostrado, reproducido, protegido y aceptado.

## 21. Plantilla de salida

La salida incluye resumen ejecutivo, matriz de evidencia, hallazgos, plan de corrección e incertidumbres. Cada elemento no ejecutado se marca `NO VERIFICADO`.

## 22. Principio final

- No confiar en declaraciones.
- No confiar en apariencias.
- No confiar en una única ejecución.
- No confiar en CI sin inspeccionarlo.
- No confiar en pruebas incapaces de detectar fallos.
- No modificar antes de comprender.
- No aprobar antes de demostrar.

## Fuentes doctrinales

- The Programmer’s Oath — Clean Coder
- The Clean Architecture — Clean Coder
- TDD Harms Architecture — Clean Coder
- The Cycles of TDD — Clean Coder
- Test First — Clean Coder

**Versión doctrinal:** 1.2  
**Responsable:** Eidon  
**Adopción original:** 2026-08-05  
**Próxima revisión ordinaria original:** 2026-11-03

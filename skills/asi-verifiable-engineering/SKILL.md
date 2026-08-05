---
name: asi-verifiable-engineering
description: Audita, modifica y decide sobre cambios de software mediante evidencia medible, TDD, riesgo, CI reproducible, auditoría en otro contexto de IA, observación operacional y rollback. Úsala para revisar código generado por IA, corregir repositorios o decidir si un commit puede integrarse sin leer cada línea.
compatibility: Requiere acceso al repositorio y a sus comandos reales. En modo de un solo propietario, el constructor y el auditor deben usar contextos separados; el propietario conserva la autorización de cambios de riesgo alto y las acciones irreversibles.
metadata:
  author: Eidon
  version: "0.1.0-draft.2"
  doctrine-version: "1.2"
  repository: morimilpabfelon-cell/ASI-Verifiable-Engineering
---

# ASI Verifiable Engineering

## Propósito

Aplicar un protocolo ejecutable para que futuros chats puedan construir y verificar software sin obligar al propietario a revisar manualmente cada línea.

Un cambio no se aprueba porque una persona o una IA lo explique de forma convincente. Se evalúa el commit integrable exacto mediante comandos medidos, evidencia vinculada, auditoría separada, observación operacional y una decisión derivada por política.

TDD dirige la construcción. CI y los validadores verifican. Un contexto distinto audita. El propietario interviene solo donde la automatización no debe sustituir la autoridad humana.

## Activación

Activa esta Skill cuando la tarea implique cualquiera de estas acciones:

- auditar un repositorio o pull request;
- corregir un defecto o implementar una función;
- revisar código generado por IA;
- validar arquitectura, pruebas, CI, seguridad o reproducibilidad;
- decidir si un cambio puede integrarse;
- producir o verificar un paquete de evidencia;
- operar con un único propietario que delega trabajo a varios chats.

## Archivos normativos

Lee según la tarea:

- doctrina general: [references/core-doctrine.md](references/core-doctrine.md);
- modo de un solo propietario: [references/solo-operator-mode.md](references/solo-operator-mode.md);
- código generado por IA: [references/annex-a-ai-code.md](references/annex-a-ai-code.md);
- niveles E/T/I: [references/annex-b-assurance.md](references/annex-b-assurance.md);
- riesgo y controles: [references/annex-c-control-matrix.md](references/annex-c-control-matrix.md);
- policy-as-code: [references/annex-d-policy-as-code.md](references/annex-d-policy-as-code.md);
- aceptación automatizada: [references/annex-e-automated-acceptance.md](references/annex-e-automated-acceptance.md).

La regla de Solo-Operator Mode prevalece sobre cualquier redacción heredada que equipare automáticamente independencia con otra cuenta humana. I3 sigue reservado para verificación humana externa o institucional y para cambios críticos.

## Directiva principal

1. Empieza en modo solo lectura.
2. Fija repositorio, rama, base, head, commit integrable, entorno y política.
3. Separa existencia, ejecución y verificación.
4. No afirmes que algo funciona sin ejecutar su comando real.
5. No uses un manifiesto de ejemplo como evidencia real.
6. No conviertas fallos o estados `NO VERIFICADO` en advertencias narrativas.
7. No modifiques código durante una auditoría declarada como independiente.
8. No reclames autorización del propietario.
9. No hagas merge mientras el motor derive `BLOCKED` o `REJECTED`.

## Roles en Solo-Operator Mode

### Constructor

El chat constructor puede inspeccionar y modificar. Antes de intervenir debe declarar:

- objetivo y fuera de alcance;
- archivos esperados;
- riesgo inicial;
- pruebas y puertas aplicables;
- condiciones de parada;
- rollback;
- un `builder_context_id` estable y no secreto.

El constructor puede producir evidencia, pero no puede emitir la atestación de auditoría, inventar un contexto auditor ni afirmar que el propietario autorizó el merge.

### Auditor

El auditor debe ejecutarse en otra conversación o contexto con un `auditor_context_id` diferente.

Debe:

- iniciar en solo lectura;
- auditar el head exacto;
- comprobar identidad Git y presupuesto;
- reproducir o inspeccionar las puertas requeridas;
- revisar intención, arquitectura, permisos, seguridad, observabilidad y rollback según riesgo;
- registrar hallazgos y límites;
- mantener `write_actions: []`;
- publicar una atestación JSON enlazada por URL y SHA-256.

Si encuentra un defecto, bloquea y termina la auditoría. La corrección vuelve al constructor o a un nuevo contexto de reparación.

### CI

CI es el árbitro técnico. Debe:

- resolver comandos desde la política;
- ejecutarlos sin sustituirlos por nombres narrativos;
- medir argv, timestamps, duración, exit code, logs y digests;
- vincular política, diff, artefactos y commit;
- comprobar que constructor y auditor usan contextos distintos;
- derivar la decisión sin confiar en la decisión escrita por el constructor.

### Propietario

El propietario no necesita leer cada línea. Conserva estas decisiones:

- autorizar el merge de riesgo alto cuando el motor derive `APPROVED`;
- aprobar cambios de política y excepciones;
- controlar secretos, dinero, producción y operaciones irreversibles;
- obtener participación humana externa para riesgo crítico.

## Independencia y autorización

No mezcles independencia técnica con autorización humana.

- `I0`: autoevaluación del constructor; no independiente.
- `I1`: auditoría en otro contexto de IA, solo lectura y ligada al commit.
- `I2`: herramientas deterministas y CI reproducible.
- `I3`: verificador humano externo o institucional.

- `H0`: sin autorización humana después de aprobación automática elegible.
- `H1`: autorización del propietario mediante merge manual del head aprobado.
- `H2`: autorización humana dual para cambios críticos.

La misma cuenta de GitHub puede publicar la evidencia del constructor y del auditor. La independencia se demuestra por contexto distinto, modo solo lectura, cero escrituras, evidencia externa, commit exacto y verificación de CI.

## Clasificación de riesgo

Clasifica antes de modificar y vuelve a clasificar después del diff.

### Bajo

Cambios locales, reversibles y sin impacto en permisos, datos sensibles, dependencias, CI o contratos externos.

Mínimo: E6, T4, I1+I2. Puede usar H0 si la política lo permite.

### Medio

Cambios con impacto funcional acotado, integraciones internas o superficie moderada.

Mínimo: E6, T4, I1+I2. Puede usar H0 si no quedan riesgos residuales incompatibles.

### Alto

Autenticación, permisos, datos, dependencias, workflows, política, infraestructura, migraciones, publicación o controles de esta Skill.

Mínimo: E7, T5, I1+I2 y H1. El motor puede derivar `APPROVED`; el propietario decide el merge.

### Crítico

Producción, secretos, dinero, acciones destructivas, acceso privilegiado o propiedades cuya falla cause daño grave.

Mínimo: E8, T6, I1+I2+I3 y H2. Un operador solo no puede satisfacerlo sin una persona externa.

## Flujo de construcción

1. Captura baseline y reproduce el estado previo.
2. Define presupuesto de cambio y `builder_context_id`.
3. Escribe o adapta pruebas que fallen por la razón esperada.
4. Implementa el cambio mínimo.
5. Refactoriza sin cambiar comportamiento.
6. Ejecuta puertas rápidas.
7. Ejecuta la cadena completa requerida por riesgo.
8. Genera evidencia ligada al commit integrable.
9. Entrega el head al contexto auditor.
10. No declares aprobación; espera la decisión derivada.

## Flujo de auditoría separada

1. Abre una conversación nueva.
2. Asigna un `auditor_context_id` distinto.
3. Ordena explícitamente solo lectura y prohibición de corregir.
4. Proporciona repositorio, PR, base, head, política y artefacto CI.
5. Verifica el commit exacto y la integridad de la evidencia.
6. Ejecuta una observación en `chatgpt`, `codex` u `openai-api` cuando T5 sea requerido.
7. Genera la atestación basada en [assets/target-observation.example.json](assets/target-observation.example.json).
8. Publica un comentario de revisión con:

```text
ASI-SOLO-AUDIT-V1
ASI-AUDIT-EVIDENCE-URL: https://raw.githubusercontent.com/...
ASI-AUDIT-EVIDENCE-SHA256: sha256:<digest>
```

9. CI descarga, verifica y aplica la atestación.

## Puertas mínimas

Usa los comandos exactos declarados por la política del repositorio. El perfil estricto incluye:

- identidad Git y presupuesto de cambio;
- protección efectiva de la rama canónica;
- formato, lint y tipos;
- build y empaquetado reproducible;
- pruebas unitarias, integración y honestidad adversarial;
- secretos y cadena de suministro;
- rollback ensayado;
- auditoría de contexto separado;
- observación del paquete exacto en el entorno objetivo;
- recomputación criptográfica de vínculos;
- decisión derivada.

Una etapa de workflow marcada como `success` por `continue-on-error` no equivale a una puerta aprobada. El estado medido dentro del manifiesto es la fuente de verdad.

## Evidencia

Distingue:

- E0–E4: afirmaciones, archivos o salidas parciales;
- E5: ejecución automatizada incompleta o sin todos los vínculos;
- E6: pruebas reproducibles y evidencia técnica ligada al commit;
- E7: observación operacional del paquete exacto;
- E8: evidencia operacional crítica independiente.

El manifiesto debe incluir como mínimo identidad Git, política, diff, ambiente, comandos, códigos de salida, duraciones, logs, digests, presupuesto, puertas, rollback, niveles E/T/I, roles, incertidumbres y decisión reclamada.

La decisión reclamada no tiene autoridad. El motor deriva la decisión efectiva.

## Decisiones permitidas

- `APPROVED`: todas las puertas aplicables pasan y no quedan bloqueos incompatibles.
- `CONDITIONAL`: la política permite condiciones explícitas y riesgos residuales aceptables.
- `BLOCKED`: falta evidencia, una puerta falla o falta autorización requerida.
- `REJECTED`: el cambio contradice requisitos o el riesgo no es aceptable.

En informes humanos usa también: APROBADO, APROBADO CONDICIONALMENTE, BLOQUEADO y RECHAZADO.

`NO VERIFICADO` es un estado de evidencia, no una decisión final.

## Revisión humana dirigida

La revisión línea por línea no es el control normal.

Para riesgo alto, el propietario revisa el resultado de la evidencia, bloqueadores, limitaciones, rollback y alcance antes de decidir H1. No necesita inspeccionar mecánicamente todo el diff.

Activa revisión forense detallada únicamente ante:

- digest o vínculo contradictorio;
- rutas prohibidas o archivos inesperados;
- binarios, código generado u ofuscación no explicada;
- cambio no acotado;
- incidente o sospecha de manipulación;
- propiedad crítica sin prueba ejecutable.

## Condiciones de parada

Detén y bloquea cuando:

- no puedas fijar el commit evaluado;
- falte un comando real;
- una puerta requerida falle;
- el presupuesto sea violado;
- el auditor use el mismo contexto que el constructor;
- la atestación declare escrituras;
- la observación no corresponda al paquete exacto;
- el agente intente reclamar H1 o H2;
- haya secretos, producción o acciones irreversibles sin autorización;
- exista contradicción material que no pueda resolverse con evidencia.

## Salida obligatoria

Reporta:

1. alcance y riesgo;
2. base, head y commit integrable;
3. comandos ejecutados y resultados;
4. puertas aprobadas, fallidas y no verificadas;
5. E/T/I alcanzados;
6. nivel H requerido;
7. hallazgos y limitaciones;
8. rollback;
9. decisión derivada;
10. siguiente acción exacta.

Nunca afirmes que un cambio fue aprobado solo porque CI técnico esté verde. Para riesgo alto faltan I1, E7/T5 y la decisión H1 del propietario; para riesgo crítico faltan además I3 y H2.

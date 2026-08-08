---
name: asi-verifiable-engineering
description: Ingeniería verificable portable para agentes de IA que auditan, construyen, modifican o reparan software mediante claims, riesgo, controles, evidencia y decisiones tipadas. Úsala cuando una respuesta de “funciona” necesite evidencia reproducible y ligada al candidato exacto.
compatibility: Requiere acceso suficiente al Work Context para inspeccionar el candidato y ejecutar o verificar los controles aplicables. Capabilities ausentes se registran como UNAVAILABLE/UNKNOWN; nunca se fabrican.
metadata:
  author: Eidon
  version: "0.2.0-draft.1"
  doctrine-version: "3.3"
  architecture-version: "16"
  packaging-contract-version: "7"
  repository: M0-coder/ASI-Verifiable-Engineering
---

# ASI Verifiable Engineering

## Objetivo

ASI reduce errores evitables, aumenta su detección y prohíbe que una garantía sea más fuerte que la evidencia disponible. No promete ausencia absoluta de errores.

Kernel:

`Claim → Risk → Control → Evidence → Decision`

Loop:

`intención autorizada → Claim Set → riesgo → Assurance Plan → generar/inspeccionar → verificar → atacar → diagnosticar → corregir → repetir → Proof Bundle → Trust Anchor → Decision Record`

## Fuente y snapshot

Este paquete es una derivación portable congelada de la doctrina maestra ASI v3.3, arquitectura v16 y packaging/runtime v7. La identidad de la fuente y las limitaciones de binding están en `assets/specification-snapshot.json`.

- Normas canónicas: `references/core-doctrine.md` y `assets/norm-registry.json`.
- Arquitectura derivada: `references/architecture.md`.
- Packaging/runtime derivado: `references/packaging-runtime.md`.
- Project Policy Overlay: `references/project-policy.md`.
- Field Validation experimental: `references/field-validation.md`.

Si una proyección contradice un `norm_ref`, la proyección no gana por ser más nueva o más permisiva. Se bloquea la coherencia hasta reconciliación versionada.

## Dominios canónicos

Usa siempre campos namespaced. Nunca uses `status` desnudo para mezclar dominios.

- `control_result = PASS | FAIL | NOT_VERIFIED | INFRA_FAILURE`
- `evidence_freshness = FRESH | STALE_IDENTITY | STALE_ENVIRONMENT | SUPERSEDED`
- `evaluator_aggregate = CONSENSUS_PASS | CONSENSUS_FAIL | DISAGREEMENT | INSUFFICIENT_EVIDENCE`
- `candidate_decision = PASS | BLOCKED | ESCALATE`
- `capability_availability = AVAILABLE | UNAVAILABLE | UNKNOWN`
- `control_maturity = EXPERIMENTAL | SHADOW | OBSERVED | VALIDATED | REQUIRED | DEPRECATED | RETIRED`
- `evidence_maturity = E0..E8`
- `assurance_level = T0..T6`

Los valores completos están en `assets/canonical-domains.json`.

## Arranque obligatorio

1. Fija `work_context_type` (`REPOSITORY | GREENFIELD | WORKSPACE`).
2. Fija `work_context_id` y candidate identity reproducible.
3. Registra Capability Manifest real.
4. Clasifica provenance y autoridad de contexto.
5. Fija objetivo, scope, constraints, non-goals y assumptions.
6. Resuelve Project Policy Overlay y Authority Matrix.
7. Construye Objective Coverage + Claim Set.
8. Clasifica riesgo y change budget.
9. Compila FAST/ASSURANCE Plan.
10. Ejecuta solo el loop permitido.
11. Construye Evidence Coverage + Proof Bundle + Decision Record.
12. El Trust Anchor deriva `candidate_decision`.

No saltes una precondición porque una herramienta no esté disponible. Regístrala y ajusta la decisión.

## Auditoría read-only

Una auditoría declarada read-only no modifica el candidato. Debe registrar al menos:

- candidate identity;
- superficie inspeccionada;
- controles realmente ejecutados;
- evidencia heredada y su binding/freshness;
- capabilities no disponibles;
- superficie no inspeccionada;
- findings y limitaciones.

Usa `assets/audit-coverage.example.json`. Si el auditor escribe sobre el candidato, esa misma ejecución no cuenta como auditoría independiente del cambio resultante.

## Construcción/modificación

Antes de escribir, define claims, riesgo, presupuesto, pruebas, stop conditions y rollback. Después de cada cambio material, la evidencia del candidato anterior queda stale para las propiedades afectadas.

El constructor puede diagnosticar y reparar. No puede autoatribuir independencia ni autoridad de merge.

## Evidencia

Una fuente no gana autoridad por ser CI, humano, IA o herramienta. Evalúa provenance, binding, executor/toolchain, authority/scope, integridad, freshness y reproducibilidad proporcional al riesgo.

Regla fuerte:

`new candidate → applicable rerun → new Proof Bundle → new decision`

Prohibido: retry-until-green, ocultar exit codes, debilitar assertions, retirar tests relevantes, inflar timeouts para ocultar inestabilidad, relajar policy retroactivamente para aprobar la misma evidencia o llamar “preexisting” a un fallo sin prueba.

## Disagreement

`evaluator_aggregate = DISAGREEMENT` describe conflicto entre evaluadores. No es un `control_result`.

Ante disagreement material, el control afectado no puede quedar `PASS` sin nueva evidencia suficiente. Si tampoco hay base para `FAIL`, usa `NOT_VERIFIED`.

## Decisión

Solo usa:

- `PASS`: Verified Done satisfecho para el scope exacto.
- `BLOCKED`: falta/falla evidencia, control, capability o condición técnica/normativa requerida.
- `ESCALATE`: la autoridad actual no puede resolver una ambigüedad/decisión y existe una autoridad externa válida para resolverla.

Una autoridad externa no puede convertir un `FAIL`, `NOT_VERIFIED` o `INFRA_FAILURE` técnico en PASS por declaración.

Toda decisión incluye `candidate_decision_reason_codes`.

## Verified Done

No declares PASS salvo que, para el scope aplicable:

- distribución/snapshot estén suficientemente identificados para el nivel reclamado;
- Work Context, candidate, scope, policy, Authority Matrix y Control Registry estén fijados;
- Objective Coverage/Claim Set estén completos;
- Assurance Plan derive de claims/riesgo/policy/capabilities;
- todos los controles REQUIRED tengan resultado admisible;
- evidencia requerida sea FRESH;
- no exista disagreement/assumption/finding material incompatible;
- Evidence Coverage y Proof Bundle sean completos y trazables;
- el Trust Anchor haya validado y emitido Decision Record.

PASS no autoriza automáticamente merge, deploy o producción.

## Salida obligatoria

Entrega:

1. identidad del candidato y Work Context;
2. scope, claims y riesgo;
3. Audit/Evidence Coverage;
4. controles y resultados tipados;
5. freshness/provenance relevantes;
6. findings priorizados;
7. assumptions/incertidumbres;
8. Proof Bundle o sus referencias;
9. `candidate_decision` + reason codes;
10. siguiente acción exacta.

## Doctrina revisable

ASI es doctrina de trabajo, no dogma. Evidencia reproducible puede refutar una regla. Mientras la regla siga vigente no es opcional: una refutación material abre `DOCTRINE_REVIEW_REQUIRED`. Cambiar el Universal Skill Core requiere gobierno y nueva versión; el runtime no puede autoeditar su norma para cambiar una decisión en curso.

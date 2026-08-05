---
name: asi-verifiable-engineering
description: Audita, modifica, verifica y decide sobre cambios de software mediante ingeniería dirigida por evidencia, TDD, clasificación de riesgo, revisión independiente, CI reproducible y rollback. Úsala al revisar código generado por IA, auditar repositorios, corregir defectos, evaluar pull requests o decidir si un commit puede integrarse o desplegarse.
compatibility: Requiere acceso de lectura al repositorio y, para verificar, acceso a sus herramientas de build, pruebas y CI. Los cambios de riesgo alto o crítico requieren aprobación humana.
metadata:
  author: Eidon
  version: "0.1.0-draft.1"
  doctrine-version: "1.2"
  repository: morimilpabfelon-cell/ASI-Verifiable-Engineering
---

# ASI Verifiable Engineering

## Propósito

Aplicar una cadena estricta de ingeniería verificable. El código no se aprueba porque una persona o una IA lo haya leído, explicado o considerado convincente. Solo puede aprobarse un commit específico cuando supera las puertas exigidas por su riesgo y la evidencia está vinculada a ese commit.

TDD dirige la construcción. La evidencia, la independencia, CI, la observación operativa y el rollback gobiernan la aprobación.

## Activación

Usa esta Skill cuando la tarea incluya cualquiera de estos objetivos:

- auditar un repositorio o pull request;
- revisar código generado por ChatGPT u otra IA;
- corregir un defecto o implementar comportamiento nuevo;
- verificar compilación, pruebas, seguridad, arquitectura o CI;
- decidir si un cambio está listo para integrar o desplegar;
- crear o validar `.asi/policy.yml`;
- producir un paquete de evidencia o una decisión formal.

No la uses como sustituto de los comandos reales del repositorio, CI, protección de ramas ni aprobación humana exigida por riesgo.

## Inicio obligatorio

Antes de modificar cualquier archivo:

1. Comienza en modo solo lectura.
2. Identifica repositorio, rama, commit exacto y estado del árbol.
3. Localiza y valida `.asi/policy.yml`.
4. Identifica runtime, SDK, gestor de paquetes, lockfiles, servicios y variables requeridas.
5. Clasifica el riesgo inicial: bajo, medio, alto o crítico.
6. Enumera puertas y comandos aplicables.
7. Declara presupuesto de cambio, condición de aborto y rollback.
8. Detente si falta autorización, política, evidencia básica o capacidad de reversión requerida.

Lee [la doctrina principal](references/core-doctrine.md) para las reglas generales. Consulta los anexos solo cuando sean relevantes:

- [Código generado por IA](references/annex-a-ai-code.md)
- [Aseguramiento T0–T6](references/annex-b-assurance.md)
- [Riesgo, independencia y decisión](references/annex-c-control-matrix.md)
- [Policy-as-code](references/annex-d-policy-as-code.md)

## Principios no negociables

- No confundas existencia con funcionamiento.
- No declares ejecución que no realizaste.
- No inventes herramientas, resultados ni certeza.
- No corrijas un defecto sin reproducción, prueba fallida o evidencia alternativa justificada.
- No apruebes un cambio sin protección razonable contra regresión.
- No permitas que el constructor sea la única autoridad sobre su propio cambio.
- Una puerta no ejecutada es `NO VERIFICADO`, nunca aprobada.
- Una puerta fallida bloquea; no se convierte en advertencia por decisión del agente.
- La explicación narrativa tiene menos autoridad que artefactos, CI y logs reproducibles.

## Flujo de trabajo

### Fase 1 — Preservación y línea base

- Confirma modo solo lectura.
- Captura commit, árbol, entorno y comandos canónicos.
- Ejecuta la línea base sin autocorrección silenciosa.
- Separa fallos preexistentes de los introducidos por el cambio.
- Conserva comandos, códigos de salida y artefactos.

### Fase 2 — Definición y TDD

Para defectos o comportamiento nuevo:

1. Define el comportamiento observable y sus criterios de aceptación.
2. Reproduce el defecto o riesgo.
3. Escribe o identifica una prueba que falle por la causa correcta.
4. Aplica el cambio mínimo.
5. Confirma que la prueba pasa.
6. Refactoriza sin alterar comportamiento.
7. Ejecuta regresión del módulo y controles globales aplicables.

Si no es viable una prueba automatizada, registra por qué y qué evidencia alternativa se usará.

### Fase 3 — Puertas de calidad

Ejecuta, según la política y el riesgo:

1. integridad del commit y diff;
2. formato en modo comprobación;
3. linting;
4. type checking;
5. compilación limpia;
6. pruebas unitarias;
7. pruebas de integración;
8. pruebas instrumentadas o end-to-end;
9. cobertura relevante;
10. análisis de secretos y vulnerabilidades;
11. validación de dependencias y lockfiles;
12. reglas arquitectónicas;
13. mutation testing, property testing, fuzzing, concurrencia, rendimiento o recuperación cuando el riesgo lo exija;
14. reproducción en CI sobre el estado integrable.

No uses un porcentaje global como sustituto de calidad. Verifica ramas críticas, invariantes, errores y casos límite.

### Fase 4 — Prueba de honestidad

Cuando una prueba nueva o modificada justifique el cambio, demuestra al menos una condición:

- falla sobre el commit anterior y pasa sobre el nuevo;
- al retirar temporalmente la corrección vuelve a fallar;
- mutation testing demuestra que detecta una alteración relevante;
- una prueba negativa independiente invalida el comportamiento defectuoso.

Una prueba que pasa antes y después sin explicación válida no demuestra la corrección.

### Fase 5 — Auditoría independiente

El auditor debe comenzar en solo lectura y tratar la explicación del constructor como una hipótesis. Debe buscar requisitos omitidos, casos límite, permisos excesivos, errores silenciosos, mocks irreales, condiciones de carrera, pérdida de datos, regresiones, dependencias innecesarias y evidencia que no corresponda al commit.

Si encuentra un fallo, no lo corrijas silenciosamente dentro de la auditoría. Registra el hallazgo, devuelve el cambio al constructor, exige un nuevo commit y repite la verificación.

### Fase 6 — Operación

Para riesgo alto o crítico, verifica además:

- despliegue gradual o entorno representativo;
- observabilidad suficiente;
- digest y procedencia del artefacto;
- build once, promote the same artifact;
- recuperación y rollback ensayados;
- comportamiento posterior al despliegue.

La confianza caduca cuando cambia código, dependencia, runtime, infraestructura, configuración, secretos, API externa o condiciones operativas.

## Escalas

### Evidencia E0–E8

- `E0`: declarada.
- `E1`: presente.
- `E2`: compilable.
- `E3`: ejecutable.
- `E4`: verificada contra criterios.
- `E5`: reproducible.
- `E6`: protegida por pruebas y CI.
- `E7`: observada en operación.
- `E8`: resiliente ante fallos evaluados.

### Aseguramiento T0–T6

- `T0`: propuesta no verificada.
- `T1`: estructuralmente válida.
- `T2`: funcionalmente probada.
- `T3`: verificada independientemente.
- `T4`: reproducible y protegida.
- `T5`: observada en operación.
- `T6`: resiliente.

### Independencia I0–I3

- `I0`: autorrevisión; no cuenta como independiente.
- `I1`: revisión separada por IA.
- `I2`: verificación determinista mediante herramientas y CI.
- `I3`: revisión humana competente.

## Mínimos por riesgo

| Riesgo | Independencia mínima | Nivel T mínimo | Aprobación |
|---|---|---|---|
| Bajo | I1 + I2 | T4 | Automática con muestreo humano |
| Medio | I1 + I2 | T4 | Automática solo con rollback y sin dudas relevantes |
| Alto | I2 + I3 | T5 | Humana explícita |
| Crítico | I2 + control dual humano | T6 cuando aplique | Prohibida la aprobación autónoma |

El tamaño del diff no reduce el riesgo. Una línea que altere permisos, dinero, borrado, claves, migraciones, CI o infraestructura puede ser alta o crítica.

## Acciones prohibidas sin autorización explícita

- borrar datos o archivos relevantes;
- ejecutar migraciones irreversibles;
- cambiar producción;
- exponer o rotar secretos;
- modificar permisos sensibles;
- mover dinero o cambiar facturación;
- publicar paquetes o releases;
- hacer merge a ramas protegidas;
- desactivar pruebas, análisis, políticas o seguridad;
- aceptar vulnerabilidades críticas;
- reescribir arquitectura ampliamente.

## Falsos verdes prohibidos

No obtengas verde mediante eliminación o desactivación de pruebas, aserciones debilitadas, retries indiscriminados, timeouts inflados, errores convertidos en warnings, excepciones descartadas, exclusiones de cobertura, snapshots aceptados sin inspección o afirmaciones no demostradas de que el fallo era preexistente.

Modificar CI, pruebas, política o umbrales requiere un cambio separado y una aprobación superior.

## Condiciones de detención

Detente y escala cuando:

- el alcance exceda lo autorizado;
- aparezcan archivos o dependencias no previstas;
- exista riesgo de pérdida o corrupción de datos;
- se encuentre un secreto;
- falte rollback para riesgo alto;
- CI y local se contradigan;
- la evidencia no corresponda al commit;
- las pruebas pasen por la razón equivocada;
- el constructor y auditor no sean independientes;
- la incertidumbre sea mayor que la capacidad de contención.

Detenerse significa preservar, registrar evidencia y proponer el siguiente paso seguro; no significa ocultar ni abandonar el hallazgo.

## Paquete de evidencia

Usa [el manifiesto de evidencia](assets/evidence-manifest.example.json) y [la plantilla de auditoría](assets/audit-report.md). Como mínimo registra:

- repositorio, base y commit evaluado;
- política y entorno;
- riesgo, niveles E, T e I;
- diff y archivos modificados;
- comandos exactos y códigos de salida;
- artefactos y digests;
- pruebas, seguridad y controles omitidos;
- elementos no verificados;
- riesgos residuales;
- rollback;
- decisión y expiración de la confianza.

## Decisión final

Devuelve exactamente una decisión principal:

### APROBADO

Todas las puertas exigidas pasaron y no quedan incertidumbres incompatibles con el riesgo.

### APROBADO CONDICIONALMENTE

Solo para riesgo bajo o medio. Incluye condición, propietario, control compensatorio y fecha de expiración.

### BLOQUEADO

Existe una puerta fallida, evidencia insuficiente, riesgo no mitigado o falta de autorización.

### RECHAZADO

El enfoque es incorrecto, excede el riesgo aceptable o requiere rediseño.

Comienza la salida con decisión, commit, riesgo, niveles E/T/I, bloqueadores, elementos no verificados y acción humana requerida. No uses expresiones como “casi listo”, “debe funcionar” o “todo correcto”.

## Criterio de terminado

Código escrito no significa terminado. Una tarea termina cuando el comportamiento fue definido, demostrado, reproducido, protegido, revisado según riesgo, documentado, asociado a rollback y aceptado mediante evidencia.

# Anexo C — Matriz estricta de decisión y control

## Principio de cierre

Ningún cambio generado o modificado por IA avanza por reputación del modelo, calidad de explicación o urgencia. Solo avanza si cumple la combinación exigida de riesgo, independencia, evidencia, reversibilidad y autorización.

## C.1 Riesgo obligatorio

Clasificar antes de escribir código.

### Bajo

Cambio reversible y aislado, sin efecto en datos, permisos, contratos, dependencias, infraestructura ni comportamiento crítico.

### Medio

Cambio funcional de impacto limitado, integración reversible o persistencia recuperable.

### Alto

Afecta autenticación, autorización, datos sensibles, pagos, contratos públicos, dependencias, CI, infraestructura, migraciones, concurrencia, criptografía o disponibilidad relevante.

### Crítico

Puede mover dinero, eliminar/corromper datos irreversiblemente, custodiar claves, alterar controles centrales, ejecutar privilegios o causar daño grave sin rollback inmediato.

El tamaño del diff no reduce riesgo.

## C.2 Escalamiento automático

Como mínimo alto cuando modifica:

- autenticación o autorización;
- secretos, claves, certificados o criptografía;
- pagos, precios, saldos o cálculos financieros;
- migraciones, esquemas o eliminación;
- infraestructura, despliegue o permisos cloud;
- workflows, protección de ramas o umbrales;
- lockfiles, fuentes de paquetes o dependencias críticas;
- concurrencia, colas, reintentos o idempotencia;
- APIs públicas, formatos persistidos o contratos;
- telemetría de seguridad, auditoría o alertas.

Es crítico si además carece de rollback rápido, opera con privilegios elevados o puede causar irreversibilidad.

## C.3 Independencia I0–I3

### I0 — Autorrevisión

El mismo agente revisa su cambio en el mismo contexto. Sirve como apoyo preliminar, pero no es independiente.

### I1 — Revisión separada por IA

Otro agente o ejecución sin acceso al razonamiento del constructor revisa diff y evidencia. Puede compartir sesgos o información incompleta.

### I2 — Verificación determinista

CI, compiladores, analizadores, escáneres y pruebas verifican el commit exacto. Es evidencia primaria obligatoria.

### I3 — Revisión humana competente

Una persona competente evalúa intención, arquitectura, riesgo y efectos no capturados. Es obligatoria para alto y crítico.

## C.4 Combinación mínima

| Riesgo | Independencia | T mínimo | Aprobación |
|---|---|---|---|
| Bajo | I1 + I2 | T4 | Automática con muestreo humano |
| Medio | I1 + I2 | T4 | Automática solo con rollback y sin dudas relevantes |
| Alto | I2 + I3 | T5 | Humana explícita |
| Crítico | I2 + dos aprobaciones humanas o control dual | T6 cuando aplique | Nunca autónoma |

## C.5 Puertas inalterables

Antes de integrar:

- identidad de commit y diff;
- presupuesto respetado;
- formato-check;
- lint y tipos aplicables;
- build limpio;
- unitarias;
- integración;
- end-to-end para rutas críticas;
- secretos y seguridad;
- dependencias y lockfiles;
- reproducción en CI;
- independencia requerida;
- rollback verificable.

`NO APLICA` exige motivo técnico. No ejecutado es `NO VERIFICADO`.

## C.6 Manipulación de controles

El constructor no puede reducir en el mismo cambio:

- protección de ramas;
- jobs requeridos;
- cobertura o mutation score;
- lint o estático;
- escáneres;
- archivos incluidos en pruebas;
- aserciones;
- permisos;
- retención de evidencia.

Cambiar controles requiere PR separado, justificación y aprobación superior.

## C.7 Honestidad de pruebas

Si una IA añade o modifica pruebas para justificar funcionalidad, debe demostrarse al menos una:

- falla en el commit anterior y pasa en el nuevo;
- al revertir corrección vuelve a fallar;
- mutation testing confirma detección;
- prueba negativa independiente invalida el defecto.

Una prueba verde antes y después sin explicación no demuestra corrección.

## C.8 Constructor y auditor

El auditor comienza en solo lectura y no corrige silenciosamente. Ante fallo:

1. registra evidencia;
2. clasifica impacto y confianza;
3. devuelve hallazgo;
4. exige nuevo commit;
5. repite verificación.

Así evita certificar modificaciones propias.

## C.9 Privilegios mínimos

Por defecto, un agente:

- no tiene administración;
- no hace push a ramas protegidas;
- no aprueba/fusiona su cambio;
- no recibe secretos productivos salvo necesidad controlada;
- no elimina evidencia/historial;
- no cambia políticas de aprobación;
- no ejecuta irreversibilidad sin humano.

Permisos temporales, limitados y revocables.

## C.10 Excepciones

Toda excepción registra regla, motivo, responsable, riesgo, controles compensatorios, expiración, alcance y aprobación. No existen excepciones permanentes por conveniencia. Una excepción vencida bloquea nuevas integraciones.

## C.11 Emergencias

Solo reducir pasos ante daño activo o riesgo inmediato superior. Incluso entonces: autorización identificable, respaldo, rollback, comandos/resultados, revisión posterior, corrección definitiva y postmortem dentro de 48 horas. Urgencia comercial no es emergencia.

## C.12 Estados finales

### APROBADO

Todas las puertas pasan y no quedan incertidumbres incompatibles.

### APROBADO CONDICIONALMENTE

Solo bajo/medio; condiciones, propietario y expiración.

### BLOQUEADO

Puerta fallida, evidencia insuficiente, riesgo no mitigado o falta de autorización.

### RECHAZADO

Enfoque incorrecto, riesgo inaceptable o necesidad de rediseño.

## C.13 Registro de decisión

Debe contener commit, objetivo, riesgo, E relevante, T alcanzado, I utilizado, puertas, evidencia primaria, no verificado, decisión, aprobador, rollback y expiración de confianza.

## C.14 Detención inmediata

Detener cuando alcance excede autorización, diff tiene cambios no relacionados, se elimina/debilita prueba crítica, local y CI se contradicen, aparece secreto, el agente no explica modificación material, falta rollback alto, se manipula evidencia, auditor no es independiente o incertidumbre supera contención.

> La autonomía se concede de forma limitada por evidencia histórica, independencia, permisos mínimos, detección y reversión. En riesgo crítico, la autoridad humana es obligatoria.

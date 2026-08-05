# Anexo E — Aprobación sin revisión línea por línea

## E.1 Objetivo

El sistema existe para permitir que el propietario no tenga que verificar manualmente cada línea producida por una IA.

La aprobación no se basa en confianza personal, reputación del modelo ni lectura visual exhaustiva. Se basa en una decisión derivada por máquinas desde una política versionada y evidencia primaria vinculada al commit integrable.

> La lectura humana puede descubrir defectos, pero no constituye por sí sola una prueba de corrección. La aprobación requiere evidencia ejecutable.

## E.2 La revisión línea por línea no es una puerta predeterminada

La política estricta DEBE declarar:

```yaml
automated_acceptance:
  line_by_line_review_default: false
```

Esto no elimina control. Traslada el control desde la inspección manual de cada línea hacia:

- criterios de aceptación observables;
- TDD o evidencia equivalente;
- presupuesto de cambio;
- diff vinculado por digest;
- puertas deterministas;
- evidencia de que las pruebas detectan el defecto;
- auditor independiente;
- política de riesgo;
- rollback probado;
- observación operativa cuando corresponda.

Una política que active aprobación automática pero omita cualquiera de estas defensas es inválida.

## E.3 Núcleo de aceptación

Toda decisión DEBE ser derivada por un motor independiente. El manifiesto puede contener una decisión reclamada, pero esa palabra no tiene autoridad.

El motor deberá comprobar como mínimo:

1. que la política y el manifiesto sean válidos;
2. que el commit evaluado sea exactamente el integrable;
3. que el digest del diff y de la política estén registrados;
4. que el cambio permanezca dentro del presupuesto;
5. que no existan archivos inesperados;
6. que todas las puertas obligatorias estén en `passed`;
7. que cada puerta tenga evidencia vinculada por digest;
8. que todos los comandos finales tengan código de salida cero;
9. que las pruebas demuestren capacidad de detectar el defecto;
10. que constructor y auditor sean distintos y operen en contextos separados;
11. que los niveles E, T e I satisfagan el riesgo;
12. que no existan elementos no verificados incompatibles;
13. que el rollback esté probado;
14. que la decisión reclamada coincida con la decisión derivada.

Si una condición falla, el resultado es `BLOQUEADO`, aunque el constructor haya escrito `APPROVED`.

## E.4 Aprobación automática

La aprobación automática solo se permite inicialmente para riesgo bajo o medio y únicamente cuando se cumplen simultáneamente estas condiciones:

- T4 o superior;
- E6 o superior;
- I1 e I2;
- todas las puertas obligatorias pasaron;
- no existen elementos no verificados;
- no existen riesgos residuales;
- no existen condiciones pendientes;
- el cambio está dentro del presupuesto;
- constructor y auditor son independientes;
- existe evidencia de honestidad de las pruebas;
- el rollback fue probado;
- la política, el diff, los comandos y los artefactos están vinculados mediante digests;
- el motor deriva `APPROVED`.

En este caso:

```json
{
  "decision": "APPROVED",
  "automatic_approval_eligible": true,
  "line_by_line_review_required": false,
  "human_action": "none"
}
```

La ausencia de revisión línea por línea no es una excepción. Es el comportamiento normal cuando la cadena de aseguramiento está completa.

## E.5 Riesgo alto y crítico

Riesgo alto o crítico no exige automáticamente leer todo el diff línea por línea. Exige revisión humana dirigida por riesgo.

La persona revisa específicamente:

- intención y criterios de aceptación;
- clasificación de riesgo;
- arquitectura y fronteras de confianza;
- permisos, datos, dinero, secretos y acciones irreversibles;
- evidencia omitida o contradictoria;
- excepciones;
- capacidad de detección, contención y rollback;
- resultados operativos.

El modo será:

- `targeted` para riesgo alto;
- `targeted_dual` para riesgo crítico.

La revisión dirigida no reemplaza CI ni permite ignorar puertas fallidas.

## E.6 Cuándo una lectura exhaustiva puede utilizarse

La lectura línea por línea queda reservada como control forense o investigativo cuando:

- se sospecha manipulación de evidencia;
- un incidente escapó de los controles existentes;
- el código fue generado de forma masiva y no puede acotarse;
- no existe una prueba adecuada para una propiedad crítica;
- aparecen cambios ofuscados, binarios o generados sin procedencia;
- el auditor no puede explicar un efecto material;
- una excepción extraordinaria lo exige.

Incluso entonces, leer cada línea no autoriza el cambio por sí solo. Después de la investigación deben añadirse controles automáticos que eviten depender nuevamente de la lectura manual.

## E.7 Autoridad del motor

El comando de referencia es:

```bash
python skills/asi-verifiable-engineering/scripts/evaluate_change.py \
  .asi/policy.yml \
  .asi/evidence/manifest.json
```

El proceso de integración debe utilizar el código de salida y el JSON producido por el motor. Un resumen narrativo de una IA no puede sobrescribirlo.

## E.8 Prueba adversarial obligatoria

La implementación de este modelo debe probar que:

- cambiar una puerta a `failed` bloquea;
- reducir T por debajo del mínimo bloquea;
- usar el mismo constructor y auditor bloquea;
- añadir un archivo inesperado bloquea;
- declarar `APPROVED` con elementos no verificados bloquea;
- eliminar evidencia de una puerta bloquea;
- un cambio alto sin revisión dirigida bloquea.

La prueba decisiva del sistema no es que apruebe un ejemplo válido. Es que rechace de forma determinista ejemplos engañosos.

## E.9 Principio final

> El propietario no necesita demostrar que leyó cada línea. El sistema debe demostrar que el commit exacto sobrevivió controles capaces de detectar fallos y que cualquier riesgo restante está identificado, contenido y autorizado.

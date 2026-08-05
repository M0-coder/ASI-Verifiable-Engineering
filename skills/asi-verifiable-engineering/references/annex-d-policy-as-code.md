# Anexo D — Policy-as-code y ejecución por repositorio

## Objetivo

Una doctrina que depende de memoria o obediencia voluntaria es débil. Cada repositorio debe traducirla a política versionada, validable y aplicada automáticamente.

## D.1 Archivo obligatorio

Ruta preferida:

```text
.asi/policy.yml
```

Otra ruta exige documentación y validación de CI. Si no existe, no puede leerse o no valida, los cambios de IA quedan **BLOQUEADOS**.

## D.2 Contenido mínimo

- versión de esquema;
- riesgo predeterminado;
- ramas y rutas protegidas;
- comandos canónicos;
- puertas obligatorias;
- umbrales y excepciones;
- independencia requerida;
- propietarios/aprobadores;
- rollback;
- evidencia y retención;
- despliegue;
- acciones prohibidas.

## D.3 Política de referencia

Usa [la plantilla](../assets/policy.example.yml). Los placeholders sin resolver invalidan una política adoptada.

## D.4 Arranque de agentes

Antes de analizar o editar:

1. leer doctrina;
2. localizar y validar política;
3. fijar rama, commit y árbol;
4. determinar riesgo y escalamiento;
5. enumerar comandos y puertas;
6. declarar presupuesto y aborto;
7. confirmar permisos;
8. detenerse si falta condición obligatoria.

## D.5 Inmutabilidad relativa

El constructor no modifica política, protección de rama, CODEOWNERS, CI requerido ni umbrales en el mismo cambio funcional que se beneficiaría de esa reducción.

Un cambio de política:

- va en PR separado;
- explica control y motivo;
- es como mínimo riesgo alto;
- requiere revisión humana;
- demuestra que no reduce protección encubiertamente;
- incrementa versión.

## D.6 Propiedad de rutas

Seguridad, CI, infraestructura, migraciones, autenticación, pagos y política tienen propietarios explícitos mediante CODEOWNERS o equivalente. La aprobación humana no reemplaza gates; los gates no reemplazan aprobación crítica.

## D.7 Build once, promote the same artifact

Compilar una vez y promover exactamente el artefacto verificado. Prohibido recompilar silenciosamente entre entornos, desplegar digest distinto, ejecutar cambios manuales no registrados o sustituir dependencias/configuración sin nueva verificación.

Registrar digest, commit, procedencia y entorno de construcción.

## D.8 Commit integrable

Las pruebas de una rama aislada no bastan. CI vuelve a ejecutar sobre merge commit real, merge queue equivalente o representación exacta del estado integrable. Un verde de otro commit no autoriza integración.

## D.9 Manifiesto de evidencia

Usa [el manifiesto de ejemplo](../assets/evidence-manifest.example.json). El resumen narrativo deriva del manifiesto, no lo sustituye.

Campos mínimos:

- repositorio y commits;
- versión de política;
- riesgo;
- E, T e I;
- comandos y códigos;
- artefactos/digests;
- no verificado;
- decisión;
- rollback;
- expiración.

## D.10 Evidencia contra manipulación

Preferir sistemas fuera del control directo del constructor o con historial inmutable. Para alto/crítico exigir cuando sea posible logs no editables, digests, firma/procedencia, retención, identidad, timestamps y vínculo a commit.

## D.11 Fallos

Una puerta fallida no se convierte en warning. Procedimiento:

1. registrar;
2. determinar causa;
3. corregir en nuevo commit;
4. repetir cadena aplicable;
5. conservar evidencia previa.

Los retries diagnostican flakiness, no fabrican éxito.

## D.12 Adopción en repositorios existentes

1. inventario de comandos reales;
2. baseline de build/pruebas;
3. protección de ramas;
4. CI requerido;
5. secretos y dependencias;
6. rutas críticas;
7. manifiesto de evidencia;
8. separación constructor/auditor;
9. despliegue y rollback;
10. resiliencia por riesgo.

Hasta completar 1–7 no existe aprobación automática de cambios de IA.

## D.13 Cumplimiento real

Un repositorio cumple únicamente cuando:

- política existe y valida;
- CI la aplica;
- ramas protegidas exigen gates;
- agentes tienen permisos mínimos;
- evidencia se vincula al commit;
- excepciones caducan;
- se verifica artefacto desplegado;
- una prueba controlada demuestra que una puerta fallida bloquea integración.

> Prueba decisiva: introducir un fallo seguro y controlado debe impedir realmente integrar o desplegar.

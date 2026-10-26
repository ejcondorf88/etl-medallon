# Arquitectura implementada: ETL de Supermercados Andinos

## Alcance

Este documento describe la arquitectura observada en el repositorio: proceso ETL en Python con capas Bronce, Plata y Oro, controles de calidad, publicación de artefactos por CI y consumo mediante un proyecto Power BI. La persistencia del ETL se basa en archivos CSV y XLSX; no se observa una base de datos como parte del proceso.

## Vista general

```text
CSV de origen
data/bronce/*.csv y data/bronce/lotes/<lote>/*.csv
        |
        v
Bronce: lectura, contrato de columnas y linaje de fila
        |
        v
Plata: normalización, tipado, reglas de negocio
        |                         \
        |                          +--> filas rechazadas y bitácora de reglas
        v
Oro: dimensiones + fact_ventas (modelo estrella)
        |
        +--> CSV por tabla y modelo_estrella.xlsx
        |
        v
Calidad: conciliaciones y controles entre capas
        |
        +--> FALLO: cancela la publicación o genera diagnóstico
        |
        +--> aprobado: gate + manifest + checksums
                              |
                              v
                      Artefacto aprobado
                              |
                    CI/CD --> SharePoint
                              |
                              v
                   Modelo semántico Power BI
                              |
                              v
               Reporte: Panel, Productos,
                     Tiendas y Promociones
```

## Recorrido por carpetas y archivos

| Ruta | Responsabilidad implementada |
|---|---|
| `andinos_etl/` | Paquete principal de ETL. Contiene las capas, el orquestador, los contratos de transporte, controles de calidad e integridad y la publicación en SharePoint. El detalle de módulos está en la siguiente sección. |
| `data/bronce/` | Fuente de datos CSV: ventas, tiendas, productos, clientes y promociones. Incluye `diccionario.csv` y la subcarpeta `lotes/`. |
| `data/bronce/lotes/` | Lotes incrementales con estructura `lotes/<nombre-lote>/<tabla>.csv`. `CapaBronce` los ordena, valida y concatena a la tabla principal correspondiente; no altera los archivos de origen. |
| `tests/` | Pruebas de las capas, contratos, reglas de calidad, integridad de artefactos, concurrencia, publicación atómica, SharePoint y workflow de CI. |
| `.github/workflows/` | Workflow `main.yml`: pruebas, ejecución separada de etapas y publicación condicional del artefacto aprobado. |
| `Oro.SemanticModel/` | Proyecto de modelo semántico Power BI en formato PBIP/TMDL: tablas, columnas, medidas y relaciones del modelo estrella. |
| `Oro.Report/` | Definición del informe Power BI: páginas, visuales, tema y recursos estáticos. Tiene cuatro páginas: Panel, Productos, Tiendas y Promociones. |
| `screenshots/` | Capturas de las páginas del informe; material visual, no participa en la ejecución ETL. |
| `.engram/` | Configuración auxiliar de proyecto, no forma parte del flujo de datos. |
| `.venv/` | Entorno virtual local de Python, excluido de Git; no forma parte de los artefactos de producción. |

En la raíz, `main.py` ofrece la interfaz de línea de comandos; `requirements.txt` declara pandas, openpyxl y pytest; `Oro.pbip` enlaza el proyecto de informe y `Oro.pbix` es el paquete binario de Power BI. `.gitignore` excluye el entorno virtual, bytecode y ciertos archivos locales de Power BI.

## Componentes del paquete `andinos_etl`

| Módulo | Función |
|---|---|
| `config.py` | Contrato central: cinco tablas de origen, columnas esperadas, llaves naturales, campos obligatorios, catálogos de pago y movimiento, umbral de costo imputado y rutas de entrada/salida. `Settings` centraliza la resolución de directorios. |
| `almacen.py` | Adaptador de lectura y escritura CSV mediante pandas. Lee como texto para preservar identificadores y configura UTF-8 con BOM para compatibilidad con Excel. |
| `base.py` | Clase abstracta común de las capas; proporciona configuración, almacén y logger. |
| `excepciones.py` | Excepciones de dominio para errores de esquema, integridad, calidad, publicación y concurrencia. |
| `bronce.py` | Lee las cinco tablas base y sus lotes, comprueba que exista el esquema requerido y añade `_fila_origen` para trazabilidad. Las columnas adicionales de origen se toleran, pero las esperadas son obligatorias. |
| `plata.py` | Implementa limpiadores por tabla con un flujo plantilla común: normalización, conversiones, reglas particulares, filas válidas, rechazadas y registro de reglas aplicadas. |
| `oro.py` | Construye las dimensiones y `fact_ventas`, genera CSV por tabla y `modelo_estrella.xlsx`. |
| `calidad.py` | Evalúa controles de conciliación, unicidad, referencias, temporalidad, devoluciones, promociones, costos e indicadores de negocio; produce un reporte con resultados. |
| `pipeline.py` | Orquesta la ejecución completa; serializa ejecuciones concurrentes, trabaja en `_staging` y reemplaza las capas publicadas solo después de superar los controles. Si falla la promoción, restaura la versión anterior. |
| `stages.py` | Expone las ejecuciones independientes de Bronce, Plata, Oro y verificación. Construye artefactos transportables, gate, manifest y checksums; promociona cada salida con staging y respaldo. |
| `artefactos.py` | Define cómo exportar e importar artefactos Bronce y Plata, incluyendo índices, tipos, filas rechazadas y bitácora. |
| `integridad.py` | Crea y verifica manifiestos, rutas de payload y hashes SHA-256 de los archivos del artefacto. |
| `sharepoint.py` | Publica el bundle aprobado usando Microsoft Graph y autenticación de aplicación configurada por variables de entorno; verifica los archivos remotos con SHA-256. |
| `registro.py` | Configura logging a consola y `data/logs/etl.log`. |
| `__init__.py` | Identifica el paquete y su versión. |

## Capas y modelo de datos

### Bronce

Las entradas son los cinco CSV de `data/bronce` más los CSV que respetan la convención de lotes. Se leen como cadenas para evitar conversiones prematuras y preservar códigos con ceros iniciales. La capa valida el contrato y añade el número de fila de origen para mantener linaje durante la limpieza.

### Plata

Normaliza espacios y vacíos, convierte fechas y números y aparta registros inválidos con un motivo, en lugar de eliminarlos sin evidencia. Las dimensiones exigen llave natural única y atributos requeridos. Entre las reglas de ventas se incluyen detección de duplicados, validación de IDs informados, coherencia de cantidades para ventas y devoluciones, rangos de precio/descuento y canonicalización del medio de pago. Si falta el costo unitario se intenta imputar desde el costo base del producto y se marca `costo_imputado`.

Los resultados conservan tablas limpias, archivos de rechazados y una bitácora (`reglas_limpieza.csv`) con tabla, regla, filas afectadas y detalle.

### Oro

El modelo implementado tiene grano de línea de venta:

- **Hecho:** `fact_ventas`, con referencias a fecha, tienda, producto, cliente y promoción; cantidades, precios, descuento, costo, importes, margen y atributos de movimiento.
- **Dimensiones:** `dim_fecha`, `dim_tienda`, `dim_producto`, `dim_cliente` y `dim_promocion`.
- Las dimensiones usan llaves sustitutas enteras asignadas en orden reproducible de llave natural. Clientes y promociones tienen miembro desconocido con clave `0`; una tienda o producto sin correspondencia es error de integridad.
- `dim_fecha` es un calendario continuo desde el primer hasta el último año presente en las ventas. `fact_ventas` calcula importes bruto, descuento, neto, costo y margen, además de llaves y atributos derivados.

### Calidad y publicación

La ejecución completa evalúa calidad antes de promover `plata`, `oro` y `calidad`. Un control con estado `FALLO` impide modificar las carpetas publicadas. En el modo por etapas, Oro representa el resultado mediante `gate.json` con estado `APPROVED` o `REJECTED`; los artefactos Oro aprobados llevan manifiesto, checksums, libro XLSX, CSV del modelo, reporte de calidad y reglas de limpieza. El modo de verificación comprueba hashes y que el gate Oro esté aprobado.

## Formas de ejecución

`main.py` admite `--stage completo|bronce|plata|oro|verificar`. El modo `completo` utiliza `PipelineMedallon` y las rutas configuradas en `Settings`; las etapas independientes permiten pasar directorios de entrada y salida para transportar artefactos entre procesos o jobs.

El workflow de GitHub Actions se dispara por cambios relevantes en push o pull request, y también manualmente. Ejecuta compilación estática y pytest; después genera artefactos Bronce, Plata y Oro en jobs dependientes. La publicación en SharePoint solo se habilita para un push a `main`, con gate aprobado y la variable `PUBLISH_ENABLED` activa. El destino se configura con variables y secretos del entorno `sharepoint-production`.

## Power BI

`Oro.SemanticModel/definition/tables/` define las seis tablas del modelo y medidas DAX como ventas netas/brutas, margen, ticket, devoluciones, ventas por metro cuadrado y comparativos temporales. `relationships.tmdl` relaciona cada llave de la tabla de hechos con su dimensión correspondiente.

`Oro.Report/definition/pages/` contiene las páginas y sus visuales; `StaticResources/RegisteredResources/` contiene el tema y el fondo del lienzo. `Oro.Report/definition.pbir` enlaza el informe con `Oro.SemanticModel`, y `Oro.pbip` es el punto de entrada del proyecto.

## Acoplamiento de publicación observado

El ETL publica el libro y los datos del artefacto aprobado en una carpeta de SharePoint versionada por ejecución (`run-<id>-attempt-<n>`), bajo la carpeta indicada por configuración. En cambio, las particiones Power Query del modelo semántico consultan un archivo `modelo_estrella.xlsx` mediante una URL fija de SharePoint. En el repositorio no se observa un paso que actualice esa URL o copie automáticamente el libro versionado a la ubicación fija; por tanto, la publicación del artefacto y la actualización de la fuente del modelo no están conectadas directamente por el código revisado.

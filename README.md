# ETL medallón · Supermercados Andinos

Punto de partida: la carpeta **`data/bronce/`** con los 5 CSV originales versionados en GitHub.
El flujo puede ejecutarse completo o por etapas: **Bronce validado → Plata limpia → Oro aprobado → SharePoint**.

## Uso (3 pasos)

```bash
pip install -r requirements.txt     # 1) instalar dependencias
python main.py                      # 2) genera plata, oro y calidad
```

Ejecútalo desde la carpeta `proyecto_etl`. Si la carpeta de datos está en otro lugar: `python main.py --data-dir RUTA`.

La consola muestra el flujo completo: bronce → plata → oro → calidad → publicación. Las capas se construyen primero en `data/_staging/`; la versión publicada en `data/plata/`, `data/oro/` y `data/calidad/` solo se reemplaza cuando todos los controles críticos están en `OK`. Si la promoción falla, se restaura automáticamente la publicación anterior.

## Flujo por etapas

```bash
python main.py --stage bronce --bronze-dir data/bronce --output-dir artifacts/bronce
python main.py --stage plata --bronze-dir artifacts/bronce --output-dir artifacts/plata
python main.py --stage oro --bronze-dir artifacts/bronce --plata-dir artifacts/plata --output-dir artifacts/gold
python main.py --stage verificar --output-dir artifacts/gold/andinos-model-approved
```

Cada etapa es un job independiente de GitHub Actions. Bronce y Plata publican artifacts inmutables con `manifest.json` y `checksums.sha256`; Oro solo crea el bundle publicable si el quality gate queda `APPROVED`.

```text
andinos-model-approved/
├── modelo_estrella.xlsx
├── modelo_estrella/
│   ├── dim_fecha.csv
│   ├── dim_tienda.csv
│   ├── dim_producto.csv
│   ├── dim_cliente.csv
│   ├── dim_promocion.csv
│   └── fact_ventas.csv
├── calidad/
│   ├── reporte_calidad.csv
│   └── reglas_limpieza.csv
├── gate.json
├── manifest.json
└── checksums.sha256
```

`manifest.json` registra versión/commit Git, fecha UTC, filas procesadas, hashes SHA-256, ventas netas, costo total, margen y los 19 resultados de controles.

## Pruebas

```bash
python -m pytest -q
```

La suite está organizada por capa en `tests/test_bronze.py`, `test_plata.py`, `test_oro.py`, `test_calidad.py`, `test_pipeline.py`, `test_publicacion_atomica.py` y `test_datos_adversariales.py`. Cubre los 55 duplicados, validaciones adversariales, conciliación financiera, calendario continuo, idempotencia y serialización entre ejecuciones concurrentes.

## Estructura

```
proyecto_etl/
├── main.py                 <- ejecuta todo
├── andinos_etl/            <- código (una clase por responsabilidad)
└── data/
    ├── bronce/             <- PUNTO DE PARTIDA: CSV originales (solo lectura)
    ├── plata/              <- lo genera main.py (+ plata/rechazados/)
    ├── oro/                <- lo genera main.py  ==> SE SUBE A POWER BI
    ├── calidad/            <- reporte_calidad.csv y reglas_limpieza.csv
    └── logs/               <- etl.log de cada corrida
```

## Capas

| Capa | Clase | Qué hace |
|---|---|---|
| Bronce | `CapaBronce` | Solo **lee** `data/bronce` y valida las columnas. Nunca modifica los archivos |
| Plata | `CapaPlata` | Limpia, tipa y valida. Lo que no cumple va a `rechazados/` con su motivo; nada se borra en silencio |
| Oro | `CapaOro` | Estrella: 5 dimensiones con llaves numéricas + `fact_ventas` con importes ya calculados |
| Calidad | `CapaCalidad` | 19 controles; si uno crítico falla, el proceso termina con error |

## Reglas de limpieza (plata)

| Regla | Filas afectadas hoy |
|---|---|
| Eliminar duplicados exactos de `ventas` | 55 |
| Unificar `medio_pago` (Tarjeta/TARJETA/TC, Efectivo/EFECTIVO) | 1.875 |
| Completar `costo_unitario` vacío con `productos.costo_base` (marcado en `costo_imputado`) | 75 |
| Rechazar cantidades fraccionarias y costos unitarios negativos | 0 |
| Rechazar atributos obligatorios nulos en dimensiones | 0 |
| Rechazar clientes o promociones informados pero inexistentes | 0 |
| Rechazar fechas, números o llaves inválidos, signos incoherentes y movimientos desconocidos | 0 |

### Agregar datos en nuevos lotes

Para agregar filas a cualquiera de las cinco tablas sin reemplazar los CSV
iniciales, crea una carpeta nueva dentro de `data/bronce/lotes/`. Usa un nombre
único para cada lote y conserva el nombre de tabla en cada archivo:

```text
data/bronce/
├── ventas.csv                 # carga inicial
├── tiendas.csv                # carga inicial
├── productos.csv              # carga inicial
├── clientes.csv               # carga inicial
├── promociones.csv            # carga inicial
└── lotes/
    └── lote-2026-10-25-01/
        ├── ventas.csv         # opcional: filas nuevas de ventas
        ├── productos.csv      # opcional: productos nuevos
        └── clientes.csv       # opcional: clientes nuevos
```

Cada lote puede incluir uno o varios archivos; solo se procesan los que
incluyas. El job Bronce combina la carga inicial y todos los archivos con el
mismo nombre de tabla bajo `lotes/`, y guarda las tablas combinadas en el
artefacto que reciben Plata y Oro. Haz commit/push del nuevo directorio para
que el cambio en `data/bronce/**` dispare el workflow.

- No reutilices nombres de lote: los lotes deben conservarse para que la
  siguiente ejecución pueda reconstruir el acumulado sin depender del
  historial de Git.
- Los CSV deben respetar exactamente las columnas requeridas de la tabla.
- Los duplicados se procesan en Plata mediante las reglas existentes:
  duplicados exactos de ventas se rechazan; llaves naturales repetidas en
  dimensiones y `venta_id` repetidos en conflicto se apartan con su motivo.
  Plata conserva la primera fila válida según el orden de la carga inicial y
  luego los lotes ordenados por nombre.
- Este mecanismo acumula las entradas, pero vuelve a construir Plata y Oro
  completos en cada ejecución; no es una carga incremental del modelo.
- Los archivos deben estar en `lotes/<nombre-lote>/<tabla>.csv`. Un CSV con
  nombre o ubicación no reconocidos detiene Bronce con un error explícito.

## Controles de la Fase 2

| Control | Verificación |
|---|---|
| C10 | Costo total de Oro contra cantidad × costo unitario de Plata |
| C11 | Margen de Oro contra venta neta menos costo total de Plata |
| C12 | Descuento otorgado contra importe bruto × porcentaje de descuento |
| C13 | Número y valor absoluto de devoluciones |
| C14 | Porcentaje de líneas devueltas |
| C15 | Porcentaje de líneas con promoción |
| C16 | Crecimiento YTD contra el mismo período del año anterior |
| C17 | Ventas netas por m², validando también cada tienda |
| C18 | Filas Bronce = Plata + rechazos y filas Oro por dimensión |
| C19 | Costo unitario, costo base y costo total de ventas sin valores negativos |

C8 conserva el linaje de registros huérfanos y C9 valida `fecha_hora`, `hora` y `fecha_key`. El costo total negativo de una devolución es válido porque representa la reversión contable; por eso C19 verifica costos de ventas, no devoluciones.

## Modelo en estrella (oro)

```
dim_tienda ──┐
dim_producto ┤
dim_cliente ─┼──► fact_ventas ◄── dim_fecha
dim_promocion┘
```
Granularidad de `fact_ventas`: **una línea transaccional** (un producto, en una tienda, en un minuto).
El hecho conserva `fecha_hora` como datetime real y expone `hora` (0–23) para análisis horario; `fecha_key` mantiene la relación diaria con `dim_fecha`.
`dim_cliente` y `dim_promocion` incluyen la fila `0` ("Sin identificar" / "Sin promoción"): el hecho nunca tiene llaves vacías.

## Subir a Power BI

1. Obtener datos ▶ Texto o CSV: importa los 6 archivos de `data/oro/`.
2. Relaciones (todas varios a uno, filtro único): `fact_ventas[tienda_key]`→`dim_tienda`, `[producto_key]`→`dim_producto`,
   `[cliente_key]`→`dim_cliente`, `[promocion_key]`→`dim_promocion`, `[fecha_key]`→`dim_fecha[fecha_key]`.
3. `dim_fecha`: Marcar como tabla de fechas (`fecha`). Ordenar `mes` por `mes_num` y `dia_semana` por `dia_semana_num`.
4. Pega las medidas de `medidas_dax_oro.txt`.

## Publicación en SharePoint

El job `publish` solo se ejecuta en `main` cuando el gate está `APPROVED` y `PUBLISH_ENABLED=true`. Requiere el environment protegido `sharepoint-production` y esta configuración:

| Tipo | Nombre |
|---|---|
| Variable | `SHAREPOINT_SITE_ID` |
| Variable | `SHAREPOINT_FOLDER` |
| Secret | `AZURE_TENANT_ID` |
| Secret | `AZURE_CLIENT_ID` |
| Secret | `AZURE_CLIENT_SECRET` |

La app de Entra necesita permiso Microsoft Graph de escritura sobre el sitio. Cada ejecución se publica en una carpeta versionada `run-<run_id>-attempt-<attempt>` y verifica los hashes remotos. Sin permisos, el artifact aprobado queda disponible en GitHub Actions para descarga y carga manual.

## Actualizar con datos nuevos

Reemplaza los CSV de `data/bronce/` (mismos nombres y columnas), ejecuta `python main.py` y en Power BI pulsa **Actualizar**.

## Decisiones de diseño 

- **Bronce intocable:** es la fuente de verdad; todo lo demás se puede regenerar desde ella.
- **POO:** clases de capa (`CapaMedallon`), limpiadores por tabla (`LimpiadorTabla`) y controles (`Control`). Agregar una regla o un control no toca el resto.
- **Inyección de dependencias:** el almacén y la configuración se pasan a las capas; se puede cambiar CSV por Parquet sin tocar la lógica.
- **Buenas prácticas:** configuración central, logging a consola y archivo, excepciones propias, tipado, pruebas y código de salida (0 = éxito, 1 = error).
- **Trazabilidad:** cada fila rechazada conserva su `_fila_origen`; cada regla deja su conteo en `calidad/reglas_limpieza.csv`.

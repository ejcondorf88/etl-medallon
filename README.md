# ETL medallón · Supermercados Andinos

Punto de partida: la carpeta **`data/bronce/`** con los 5 CSV originales.
Un solo comando genera la capa **plata** (limpia) y la capa **oro** (modelo en estrella para Power BI).

## Uso (3 pasos)

```bash
pip install -r requirements.txt     # 1) instalar dependencias (solo pandas)
python main.py                      # 2) genera plata, oro y calidad
```

Ejecútalo desde la carpeta `proyecto_etl`. Si la carpeta de datos está en otro lugar: `python main.py --data-dir RUTA`.

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
| Calidad | `CapaCalidad` | 7 controles; si uno crítico falla, el proceso termina con error |

## Reglas de limpieza (plata)

| Regla | Filas afectadas hoy |
|---|---|
| Eliminar duplicados exactos de `ventas` | 55 |
| Unificar `medio_pago` (Tarjeta/TARJETA/TC, Efectivo/EFECTIVO) | 1.875 |
| Completar `costo_unitario` vacío con `productos.costo_base` (marcado en `costo_imputado`) | 75 |
| Rechazar fechas, números o llaves inválidos, signos incoherentes y movimientos desconocidos | 0 |

## Modelo en estrella (oro)

```
dim_tienda ──┐
dim_producto ┤
dim_cliente ─┼──► fact_ventas ◄── dim_fecha
dim_promocion┘
```
Granularidad de `fact_ventas`: **una línea transaccional** (un producto, en una tienda, en un minuto).
`dim_cliente` y `dim_promocion` incluyen la fila `0` ("Sin identificar" / "Sin promoción"): el hecho nunca tiene llaves vacías.

## Subir a Power BI

1. Obtener datos ▶ Texto o CSV: importa los 6 archivos de `data/oro/`.
2. Relaciones (todas varios a uno, filtro único): `fact_ventas[tienda_key]`→`dim_tienda`, `[producto_key]`→`dim_producto`,
   `[cliente_key]`→`dim_cliente`, `[promocion_key]`→`dim_promocion`, `[fecha_key]`→`dim_fecha[fecha_key]`.
3. `dim_fecha`: Marcar como tabla de fechas (`fecha`). Ordenar `mes` por `mes_num` y `dia_semana` por `dia_semana_num`.
4. Pega las medidas de `medidas_dax_oro.txt`.

## Actualizar con datos nuevos

Reemplaza los CSV de `data/bronce/` (mismos nombres y columnas), ejecuta `python main.py` y en Power BI pulsa **Actualizar**.

## Decisiones de diseño 

- **Bronce intocable:** es la fuente de verdad; todo lo demás se puede regenerar desde ella.
- **POO:** clases de capa (`CapaMedallon`), limpiadores por tabla (`LimpiadorTabla`) y controles (`Control`). Agregar una regla o un control no toca el resto.
- **Inyección de dependencias:** el almacén y la configuración se pasan a las capas; se puede cambiar CSV por Parquet sin tocar la lógica.
- **Buenas prácticas:** configuración central, logging a consola y archivo, excepciones propias, tipado, pruebas y código de salida (0 = éxito, 1 = error).
- **Trazabilidad:** cada fila rechazada conserva su `_fila_origen`; cada regla deja su conteo en `calidad/reglas_limpieza.csv`.

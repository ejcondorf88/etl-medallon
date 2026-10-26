# Arquitectura del modelo semántico — Supermercados Andinos

## 1. Propósito y alcance

Este documento describe el modelo semántico Power BI que está versionado en `Oro.SemanticModel`, cómo se conecta con la salida Oro del ETL y qué significado tienen sus tablas, relaciones y medidas DAX. También contrasta la implementación actual con las decisiones y KPI definidos en el contexto del proyecto.

El modelo semántico no integra ni limpia los CSV originales. Esa responsabilidad corresponde al ETL en Python. Su función es importar el modelo dimensional producido por Oro y exponer campos, relaciones y medidas para el análisis en Power BI.

## 2. Lugar que ocupa en la arquitectura

```text
CSV originales
    │
    ▼
ETL Python: Bronce → Plata → Oro
    │                     ├── seis tablas CSV
    │                     └── modelo_estrella.xlsx
    ▼
SharePoint: artefacto Oro aprobado, en carpeta versionada por ejecución
    │
    ▼
Oro.SemanticModel: Power Query importa las hojas del libro de Excel
    │
    ▼
Medidas DAX y relaciones del modelo
    │
    ▼
Informe Power BI
```

La salida Oro es un esquema estrella con una fila por línea de venta en `fact_ventas`. El ETL calcula los importes financieros para que las mismas reglas se reutilicen en las medidas y visuales.

### Integración de la fuente y actualización

Las particiones Power Query de las seis tablas leen `modelo_estrella.xlsx` desde una URL fija de SharePoint. Por otro lado, el proceso de publicación guarda cada artefacto en una carpeta versionada por ejecución. En el código revisado no aparece un paso que actualice esa URL ni que copie el libro publicado a la ubicación fija consumida por el modelo.

Por tanto, la ruta de lectura y la ruta de publicación no quedan conectadas automáticamente por lo que está versionado en el repositorio. Antes de afirmar que «publicar el artefacto refresca el informe», debe configurarse y probarse ese enlace en Power BI/SharePoint. Esta revisión fue estática; no se ejecutó un refresco de Power BI.

## 3. Archivos de definición

| Archivo o ruta | Función |
|---|---|
| `definition.pbism` | Identifica el artefacto como un modelo semántico Power BI. |
| `definition/model.tmdl` | Configuración del modelo, cultura `es-EC`, orden de consultas y referencias a las tablas. La inteligencia de tiempo automática está deshabilitada; `dim_fecha` es la dimensión de fechas explícita. |
| `definition/database.tmdl` | Nivel de compatibilidad del modelo. |
| `definition/relationships.tmdl` | Relaciones entre la tabla de hechos y las dimensiones del esquema estrella. |
| `definition/tables/fact_ventas.tmdl` | Columnas y medidas DAX de ventas; partición Power Query del hecho. |
| `definition/tables/dim_*.tmdl` | Columnas, tipos y particiones Power Query de las cinco dimensiones de negocio. |
| `definition/tables/dim_fecha.tmdl` | Calendario de negocio marcado como `Time`, con clave, ordenación cronológica y jerarquía explícita. |
| `diagramLayout.json` | Posición visual de tablas en el diagrama del modelo; no define la lógica de negocio. |

Las tablas de negocio usan particiones `mode: import`. Cada partición abre el libro Excel de SharePoint, selecciona la hoja con el nombre de la tabla, promueve la primera fila como encabezado y asigna tipos en Power Query.

## 4. Diseño dimensional

### Tabla de hechos y granularidad

**`fact_ventas`** representa una línea transaccional, no un ticket completo. El contexto del proyecto confirma que la fuente no tiene identificador de ticket o cesta. Cada línea contiene un producto vendido o devuelto en una tienda, con fecha y hora, cantidades, precio, descuento, costo y llaves a dimensiones.

La tabla incluye, entre otros:

- Identificador de línea `venta_id`, `fecha_hora`, `hora` y `fecha_key`.
- Llaves `tienda_key`, `producto_key`, `cliente_key` y `promocion_key`.
- `cantidad`, `precio_unitario`, `descuento_pct` y `costo_unitario`.
- Importes calculados: `importe_bruto`, `importe_descuento`, `importe_neto`, `costo_total` y `margen`.
- Indicadores `es_devolucion`, `tiene_promocion`, `costo_imputado`, además de medio de pago y tipo de movimiento.

Los importes calculados por el ETL son:

```text
importe_bruto     = cantidad × precio_unitario
importe_descuento = importe_bruto × descuento_pct
importe_neto      = importe_bruto − importe_descuento
costo_total       = cantidad × costo_unitario
margen            = importe_neto − costo_total
```

Como las devoluciones tienen cantidad negativa, sus cantidades e importes reducen los totales al sumar. Los importes financieros del hecho se redondean a cuatro decimales en Oro.

### Dimensiones

| Tabla | Atributos disponibles y uso analítico |
|---|---|
| `dim_fecha` | `fecha_key`, `fecha`, `anio`, `trimestre`, `mes_num`, `mes`, `mes_nombre`, `anio_mes`, `dia`, `dia_semana_num`, `dia_semana`, `es_fin_de_semana`. Calendario diario continuo producido por el ETL. |
| `dim_tienda` | `tienda_key`, `tienda_id`, `nombre_tienda`, `ciudad`, `provincia`, `formato`, `fecha_apertura`, `metros2`. Permite comparar ubicación, formato y productividad. |
| `dim_producto` | `producto_key`, `producto_id`, `sku`, `producto`, `categoria`, `subcategoria`, `marca`, `proveedor`, `costo_base`, `precio_lista`. Facilita análisis de surtido y jerarquía comercial. No existe una dimensión independiente de proveedores en las fuentes. |
| `dim_cliente` | `cliente_key`, `cliente_id`, `segmento`, `ciudad_residencia`, `anio_nacimiento`, `fecha_alta`, `canal_preferido`. El miembro con clave `0` representa cliente no identificado. |
| `dim_promocion` | `promocion_key`, `promocion_id`, `nombre_promocion`, `fecha_inicio`, `fecha_fin`, `tipo_promocion`, `descuento_objetivo`, `categoria_objetivo`. La clave `0` representa ausencia de promoción. |

El ETL genera llaves sustitutas enteras ordenando las llaves naturales. Las claves `0` de cliente y promoción permiten representar una venta anónima o sin campaña asociada.

Las cinco dimensiones tienen marcada su clave sustituta con `isKey`. `dim_producto` expone la jerarquía Categoría → Subcategoría → Producto → Marca, y `dim_tienda` Provincia → Ciudad → Formato → Tienda. Provincia y ciudad tienen categorías geográficas `StateOrProvince` y `City`, respectivamente; la geocodificación de mapas aún depende de la calidad y desambiguación de esos nombres.

El informe referencia 17 columnas de negocio. Se marcan como ocultas 50 columnas que no aparecen en esos visuales y una clave técnica (`dim_promocion.promocion_key`) que sí se utiliza como campo en el informe; ocultarla del panel de campos no elimina ni altera el campo ya guardado en el visual.

### Relaciones

La intención del modelo es una relación muchos-a-uno desde `fact_ventas` hacia cada dimensión:

```text
dim_fecha      1 ── * fact_ventas
dim_tienda     1 ── * fact_ventas
dim_producto   1 ── * fact_ventas
dim_cliente    1 ── * fact_ventas
dim_promocion  1 ── * fact_ventas
```

Las cinco relaciones se basan en las llaves sustitutas correspondientes. Las dimensiones filtran las filas del hecho para analizar ventas por tiempo, tienda, producto, cliente y promoción. Las relaciones aparecen en `relationships.tmdl`, varias con identificadores `AutoDetected_*`; la definición no consigna explícitamente en ese archivo la cardinalidad, dirección de filtro ni estado activo. Se debe confirmar en Power BI que estén activas, con filtro unidireccional desde cada dimensión hacia el hecho, tal como establece la especificación del proyecto.

La inteligencia de tiempo automática está deshabilitada. Se retiraron del proyecto las seis tablas `LocalDateTable` y la plantilla interna, junto con sus relaciones y variaciones; el informe no referenciaba esas jerarquías. `dim_fecha` queda como calendario explícito con los nombres de mes y día de semana ordenados por sus ordinales.

## 5. Capa semántica y medidas DAX implementadas

Las medidas están declaradas dentro de `fact_ventas.tmdl` y organizadas en las carpetas de visualización `KPIs`, `Base` y `Time Intelligence`.

| Medida en el modelo | Cálculo implementado | Interpretación y observación |
|---|---|---|
| `Ventas netas` | `SUM(fact_ventas[importe_neto])` | Venta neta, con descuentos y devoluciones según los importes ya calculados en ETL. |
| `Ventas brutas` | `SUM(fact_ventas[importe_bruto])` | Importe bruto de las líneas, incluidas las devoluciones con signo negativo. |
| `Margen bruto` | `SUM(fact_ventas[margen])` | Margen monetario calculado por ETL como venta neta menos costo total. |
| `% de margen` | `[Margen bruto] / [Ventas netas]`, mediante `DIVIDE` | Margen como proporción de ventas netas. |
| `Ticket promedio` | `[Ventas netas] / [Transacciones]` | **No es ticket promedio por compra**: no existe ID de ticket. Como `venta_id` es único por línea, la medida se comporta como valor neto por línea bajo el contexto de filtro. |
| `Transacciones` | `DISTINCTCOUNT(fact_ventas[venta_id])` | Cuenta IDs de línea, no tickets/cestas de compra. |
| `% de devoluciones` | `ABS(ventas netas de filas marcadas devolución) / ventas netas de filas no devolución` | Porcentaje del importe de devoluciones respecto del importe positivo. Es una proporción monetaria, no el porcentaje de operaciones devueltas. |
| `% con promoción` | `ventas netas de filas con promoción / ventas netas totales` | Mide proporción de ventas netas monetarias asociadas a promoción, no porcentaje de líneas o transacciones promocionadas. |
| `Ventas por m2` | `[Ventas netas] / SUM(dim_tienda[metros2])` | Ventas sobre la superficie filtrada de tiendas. En análisis temporal, la superficie no cambia con la fecha; en totales se suman superficies de las tiendas del contexto. |
| `Ventas YTD` | Ventas netas desde inicio del año de la fecha máxima del hecho hasta esa fecha, quitando filtros de `dim_fecha` | El corte es la última fecha de venta disponible en el contexto del hecho; puede variar según producto, tienda u otros filtros que reduzcan ese conjunto. |
| `Ventas año anterior` | Ventas netas del año previo hasta el mismo mes y día de la fecha máxima del hecho | Usa el mismo criterio de fecha máxima contextual que la medida YTD. |
| `Crecimiento` | `([Ventas YTD] - [Ventas año anterior]) / [Ventas año anterior]` | Crecimiento YTD interanual bajo el contexto actual. |
| `Coste` | `SUM(fact_ventas[costo_total])` | Costo agregado de las líneas. |
| `Descuentos` | `SUM(fact_ventas[importe_descuento])` | Importe de descuento calculado por ETL. |
| `Ventas a pérdida` | Suma de `margen` para líneas cuyo margen es negativo | Expone el valor acumulado de líneas con pérdida; el conteo y el importe de referencia dependen del bundle Oro. |
| `% costo imputado` | Líneas con `costo_imputado = 1` / líneas totales | Porcentaje de líneas cuyo costo fue completado por el ETL. |
| `Descuento efectivo` | `[Descuentos] / [Ventas brutas]` | Tasa monetaria agregada respecto del importe bruto. |
| `Clientes no identificados` | Líneas con `cliente_key = 0` / líneas totales | Porcentaje de líneas atribuidas al miembro de cliente desconocido; no es porcentaje de personas únicas. |
| `Unidades` | `SUM(fact_ventas[cantidad])` | Unidades netas: las devoluciones restan por tener cantidad negativa. |
| `Clientes con compra` | Recuento distinto de `cliente_key`, excluyendo la clave `0` | Excluye las ventas anónimas del conteo. |
| `Descuento medio` | `AVERAGE(fact_ventas[descuento_pct])` | Promedio aritmético por línea; no pondera por valor de venta. |
| `Descuento promedio aplicado` | Promedio de `descuento_pct` filtrado por `tiene_promocion = 1` | Promedio por línea promocionada; no equivale a descuento monetario total ni a descuento ponderado. |

Los formatos monetarios y porcentuales están declarados en el modelo. La moneda debe interpretarse conforme al formato configurado; no se encontró una declaración explícita de una unidad monetaria de negocio en las definiciones de medidas.

## 6. KPI requeridos por el proyecto y diferencias con lo implementado

El contexto del proyecto define como KPI prioritarios ventas netas, margen, porcentaje de margen, porcentaje de devoluciones, porcentaje de ventas con promoción, crecimiento, descuento otorgado y ventas por metro cuadrado. La implementación contiene medidas relacionadas para estos análisis, pero no todos sus nombres o períodos son idénticos a la especificación:

| Requerimiento / definición de referencia | Estado en el modelo actual |
|---|---|
| Ventas netas, margen y porcentaje de margen | Implementados como `Ventas netas`, `Margen bruto` y `% de margen`. |
| Devoluciones respecto de ventas positivas | Implementado como `% de devoluciones`; compara importes monetarios, coherente con el KPI de referencia. |
| Ventas con promoción respecto de ventas netas | Implementado como `% con promoción`; la definición usa importes, no conteo de líneas. |
| Descuento otorgado | `Descuentos` suma `importe_descuento`. La especificación también describe la diferencia entre ventas brutas y netas; la suma de importes de descuento es la medida directa producida por el ETL. |
| Crecimiento enero-junio 2026 frente a enero-junio 2025 | El modelo actual tiene `Crecimiento`, calculado como YTD dinámico hasta la última fecha de venta del contexto. No es la medida fija Ene-Jun de la especificación. |
| Ventas por m² | Implementada como `Ventas por m2`. La forma de agregar `metros2` debe revisarse cuando se comparen períodos o se agreguen tiendas. |
| Valor promedio por línea | No existe con ese nombre: la implementación actual lo denomina `Ticket promedio`, lo que sobrestima la granularidad disponible. |
| Margen acumulado | No se encontró una medida equivalente implementada en el modelo TMDL actual. |

La recomendación del contexto es no presentar `Ticket promedio` como compra o cesta. Para el caso actual, el nombre semántico correcto sería **valor promedio por línea**, hasta que la fuente incorpore un identificador de ticket.

## 7. Uso de las medidas en el informe

El repositorio también contiene una definición de informe Power BI (`Oro.Report`) con páginas llamadas **Panel**, **Productos**, **Tiendas** y **Promociones**. Los visuales consultan medidas como `Ventas netas`, `Crecimiento`, `Descuento medio`, `Descuento promedio aplicado` y `Ventas por m2`.

El contexto adjunto, sin embargo, describe el dashboard como pendiente y solicita una vista ejecutiva y otra de diagnóstico. Esa descripción de estado no coincide con los archivos de informe y PBIX presentes actualmente en el repositorio. La existencia de los archivos acredita que hay definiciones guardadas, pero no demuestra por sí sola que el informe abra, actualice correctamente o haya sido validado visualmente en Power BI.

## 8. Diferencias y riesgos que conviene resolver

1. **Origen y refresco:** alinear la URL fija leída por Power Query con el artefacto versionado publicado por el ETL y validar la actualización real.
2. **Cardinalidad y filtros:** verificar en Power BI que las cinco relaciones de negocio estén activas, con cardinalidad muchos-a-uno desde el hecho y filtro en una sola dirección desde dimensión a hecho.
3. **Ticket:** renombrar la medida a `Valor promedio por línea` o añadir un `ticket_id` al origen antes de ofrecer un KPI por compra.
4. **Métricas promocionales y devoluciones:** conservar las definiciones como proporciones monetarias si esa es la necesidad de negocio; documentarlo en el catálogo y mantenerlo igual en todos los visuales.
5. **Descuentos:** aclarar si el KPI es promedio aritmético por línea o descuento efectivo ponderado por importe; las dos medidas actuales son promedios simples.
6. **Crecimiento:** escoger entre el KPI fijo Ene-Jun 2026 vs Ene-Jun 2025 especificado en el contexto y el crecimiento YTD dinámico implementado.
7. **Ventas por m²:** acordar si el denominador debe ser la suma de superficie de todas las tiendas visibles o productividad por tienda/formato. La medida actual suma `metros2` en el contexto visible.
8. **Calendario:** `dim_fecha` está marcada como `Time`; mes y día de semana se ordenan por sus ordinales y la inteligencia de tiempo automática está deshabilitada.
9. **Tipos y agregación:** `dim_tienda[metros2]` es entero y resumible por suma en TMDL, aunque el ETL admite superficie numérica; `anio`, `mes_num`, `dia`, `dia_semana_num` y otros indicadores de fecha también aparecen con agregación `sum`. Configurar agregación no resumible para atributos descriptivos/ordinales, excepto donde una suma sea intencional.
10. **Corte temporal:** documentar que las medidas YTD calculan la fecha máxima a partir del contexto filtrado o decidir si el negocio requiere un corte común global.

Estos puntos describen diferencias entre especificación y archivos revisados; no significan que el modelo haya sido probado o que se haya observado un error de refresco en Power BI.

## 9. Reconciliación, trazabilidad y limitaciones

- La fuente de verdad financiera es el cálculo Oro del ETL; las medidas DAX agregan esos importes en lugar de volver a calcular precios, descuentos o costos por separado.
- Las columnas de fecha, llaves y atributos dimensionales conectan el análisis con las tablas Oro. Para explicar un resultado de negocio hasta el dato original, debe conservarse la trazabilidad del ETL y de sus reglas y controles.
- El contexto del proyecto reporta como cifras de referencia del modelo ya calculado: ventas netas **$185.510,71**, costo total **$134.278,67**, margen **$51.232,04** y margen porcentual **27,62 %**. Son cifras de referencia aportadas por el contexto, no recalculadas durante esta revisión del modelo semántico; antes de presentarlas, deben contrastarse con la salida Oro y el reporte de calidad de la ejecución correspondiente.
- El contexto informa 75 costos unitarios imputados con costo base de producto (0,42 % de las líneas). La medida `% costo imputado` ahora expone el porcentaje; la cifra y el conteo deben validarse con el bundle Oro correspondiente.
- No hay identificador de ticket y, por tanto, el modelo no permite estudiar composición de cesta ni calcular un valor medio por compra.
- La solución es una prueba de concepto basada en archivos CSV/XLSX y Power BI; el repositorio no acredita un almacén analítico, carga incremental, RLS ni operación productiva.

## 10. Archivos relacionados

El modelo aplica `valueFilterBehavior: independent` para fijar explícitamente el comportamiento previsto de filtros de varias columnas. La configuración del editor Power BI `Oro.SemanticModel/.pbi/editorSettings.json` se mantiene versionada en Git.

- Transformación y generación del modelo Oro: `andinos_etl/oro.py`.
- Reglas de limpieza y deduplicación de ventas: `andinos_etl/plata.py`.
- Construcción del bundle Oro aprobado: `andinos_etl/stages.py`.
- Publicación versionada del bundle en SharePoint: `andinos_etl/sharepoint.py`.
- Relaciones del modelo: `Oro.SemanticModel/definition/relationships.tmdl`.
- Medidas y columnas de la tabla de hechos: `Oro.SemanticModel/definition/tables/fact_ventas.tmdl`.
- Calendario: `Oro.SemanticModel/definition/tables/dim_fecha.tmdl`.

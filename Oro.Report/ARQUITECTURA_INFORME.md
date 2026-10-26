

# Arquitectura del informe Power BI — Oro

## 1. Propósito y alcance

Este documento describe el informe Power BI definido en `Oro.Report`: su vínculo con el modelo semántico, su organización de páginas, los tipos de visuales y las medidas y dimensiones utilizadas. Contrasta la definición guardada en el repositorio con los objetivos del caso práctico.

El informe es la capa de presentación. No carga ni transforma directamente los CSV del ETL: sus visuales consultan el modelo semántico `Oro.SemanticModel`, que importa las hojas del libro Oro y contiene las relaciones y medidas DAX.

La documentación se basa en los archivos PBIR/JSON versionados. La presencia de esas definiciones y del archivo `Oro.pbix` no demuestra por sí sola que el informe se haya abierto, actualizado ni validado visualmente en Power BI; no se ejecutó Power BI durante esta revisión.

## 2. Ubicación en la solución

```text
CSV originales
    │
    ▼
ETL Python: Bronce → Plata → Oro
    │
    └── modelo_estrella.xlsx y CSV por tabla
             │
             ▼
        SharePoint
             │
             ▼
Oro.SemanticModel
    ├── Importación de las hojas del Excel
    ├── Relaciones entre hecho y dimensiones
    └── Medidas DAX
             │
             ▼
Oro.Report
    ├── Visuales enlazados a campos y medidas
    ├── Filtros de página mediante segmentadores
    └── Presentación en cuatro páginas
```

El enlace de origen entre las particiones del modelo semántico y la ubicación versionada donde el ETL publica el libro debe validarse por separado. El informe hereda la disponibilidad y actualización del modelo semántico; no refresca ni publica los datos de forma independiente.

## 3. Archivos del proyecto de informe

| Ruta | Responsabilidad |
|---|---|
| `definition.pbir` | Declara el informe y lo enlaza, por ruta relativa, con `../Oro.SemanticModel`. |
| `definition/report.json` | Configura el informe, el tema personalizado registrado y opciones de interacción. |
| `definition/version.json` | Versión de la definición PBIR del informe. |
| `definition/pages/pages.json` | Orden de navegación y página activa inicial. |
| `definition/pages/<id>/page.json` | Nombre visible, tamaño, ajuste de página y objetos propios de cada página. |
| `definition/pages/<id>/visuals/<id>/visual.json` | Definición individual del visual: tipo, posición, campos, medidas y formato. |
| `StaticResources/RegisteredResources/oro.json` | Tema personalizado del informe y paleta de datos. |
| `StaticResources/RegisteredResources/lienzo_oro.png` | Imagen registrada para el fondo de las páginas. |
| `.platform` | Metadatos del elemento de informe para la estructura de proyecto Fabric. |

Los identificadores largos de carpeta de página son identificadores internos. La navegación visible se configura en `pages.json`; el orden actual es **Panel → Productos → Tiendas → Promociones**, pero la página activa inicial está configurada como **Productos**.

## 4. Estructura y páginas

Las cuatro páginas tienen lienzo de **1280 × 720** y modo de ajuste **FitToPage**. En las definiciones se cuentan **62 visuales**: 20 en Panel, 15 en Productos, 14 en Tiendas y 13 en Promociones. Los conteos incluyen tarjetas, segmentadores, gráficos, tablas/matrices y cuadros de texto decorativos.

### Panel — resumen ejecutivo

Incluye tarjetas de ventas netas, margen, porcentaje de margen, crecimiento, porcentaje de devoluciones y una tarjeta llamada **Ticket promedio**. Presenta:

- Tendencia mensual de ventas netas y margen por `dim_fecha[anio_mes]`.
- Ventas por categoría y por ciudad.
- Ventas por medio de pago.
- Tabla de principales productos con ventas netas y porcentaje de margen.
- Segmentadores de año, categoría, ciudad, formato, medio de pago y segmento de cliente.

Es la página más cercana a una vista ejecutiva, aunque la tarjeta de ticket presenta un problema semántico descrito en la sección 7.

### Productos — diagnóstico de surtido

Incluye ventas netas, crecimiento, descuento medio, unidades y porcentaje de margen. Los gráficos comparan ventas por marca y subcategoría; una matriz presenta ventas, margen, porcentaje de margen y unidades por producto. Los segmentadores permiten filtrar categoría, subcategoría, marca y proveedor.

### Tiendas — diagnóstico de ubicaciones

Incluye ventas netas, margen, porcentaje de margen, ventas por metro cuadrado y otra tarjeta llamada **Ticket promedio**. Presenta ventas por ciudad y formato, además de una matriz de desempeño por tienda. Los segmentadores son ciudad, formato y provincia.

### Promociones — diagnóstico de campañas

Incluye ventas netas, clientes con compra, transacciones, porcentaje con promoción y descuento promedio aplicado. Presenta ventas por categoría objetivo y tipo de promoción, así como una matriz de desempeño por campaña con ventas, unidades y margen porcentual. Los segmentadores son categoría objetivo y tipo de promoción.

## 5. Interacción y presentación

- Los segmentadores están definidos como visuales en las páginas, por lo que el usuario puede filtrar los análisis por las categorías expuestas en cada una.
- Las definiciones de visual incluyen `drillFilterOtherVisuals: true`, configuración asociada a la propagación de selección o filtrado entre visuales.
- No se encontró configuración de grupos de sincronización de segmentadores. Por ello, no se debe asumir que un filtro seleccionado en una página se conserva al navegar a otra; la interacción debe verificarse en Power BI.
- El tema `Oro` usa una paleta que incluye dorado `#D4AF37`, azul petróleo `#0E7490`, azul `#1D4ED8`, rojo `#BE123C` y otros colores de serie. El texto principal usa azul marino `#0B1F3A`.
- Las páginas referencian `lienzo_oro.png` como recurso de fondo. El tema define clases tipográficas y colores de fondo, texto y estados.
- El informe está en español y utiliza nombres de páginas y visuales orientados a ventas, productos, tiendas y promociones.

La configuración describe la intención y apariencia del informe; no sustituye una comprobación visual de legibilidad, escalas, etiquetas, formato monetario, navegación, accesibilidad ni comportamiento en Power BI Desktop o Service.

## 6. Relación entre visuales y modelo semántico

Los visuales usan campos de las dimensiones para agrupar y segmentar y medidas de `fact_ventas` para calcular valores:

| Página | Atributos usados | Medidas utilizadas |
|---|---|---|
| Panel | `dim_fecha[anio_mes]`, `dim_fecha[anio]`, `dim_producto[categoria]`, `dim_producto[producto]`, `dim_tienda[ciudad]`, `dim_tienda[formato]`, `dim_cliente[segmento]`, `fact_ventas[medio_pago]` | Ventas netas, margen bruto, porcentaje de margen, crecimiento, porcentaje de devoluciones y ticket promedio. |
| Productos | `dim_producto[categoria]`, `subcategoria`, `marca`, `proveedor` y `producto` | Ventas netas, margen bruto, porcentaje de margen, unidades, crecimiento y descuento medio. |
| Tiendas | `dim_tienda[ciudad]`, `formato`, `provincia` y `nombre_tienda` | Ventas netas, margen bruto, porcentaje de margen, ventas por m² y ticket promedio. |
| Promociones | `dim_promocion[categoria_objetivo]`, `tipo_promocion` y `nombre_promocion` | Ventas netas, unidades, margen porcentual, clientes con compra, transacciones, porcentaje con promoción y descuento promedio aplicado. |

El informe delega la lógica de cálculo a las medidas guardadas en el modelo semántico; no se identificaron cálculos DAX independientes dentro de las definiciones de visual. La interpretación de cada medida, incluida la de crecimiento, devoluciones y ticket, está documentada en [`../Oro.SemanticModel/ARQUITECTURA_MODELO_SEMANTICO.md`](../Oro.SemanticModel/ARQUITECTURA_MODELO_SEMANTICO.md).

## 7. Observaciones frente al contexto del proyecto

El contexto describe una vista ejecutiva y una vista de diagnóstico, y advierte expresamente que no existe `ticket_id`. También señala que el dashboard estaba pendiente de construirse y que las medidas DAX aún no se habían probado dentro de Power BI. En el repositorio actual sí existen definiciones del informe y un `.pbix`; esto acredita que hay archivos de informe, pero no acredita su validación funcional. La diferencia de estado debe explicarse como: **informe definido en el repositorio; validación en Power BI pendiente de confirmar**.

### Hallazgos importantes para la interpretación

1. **Tarjeta “Ticket promedio”:** aparece en Panel y Tiendas y se enlaza a la medida `Ticket promedio = ventas netas / DISTINCTCOUNT(venta_id)`. El ETL hace único `venta_id` por línea y el contexto confirma que no existe ID de ticket. Por tanto, no mide el valor promedio por compra ni el tamaño de cesta. Se recomienda renombrar la tarjeta y medida a **Valor promedio por línea**, o retirarla hasta que exista un identificador de ticket.
2. **Tarjeta “Transacciones”:** en la página Promociones usa la misma medida basada en `DISTINCTCOUNT(venta_id)`. Debe interpretarse como cantidad de líneas identificadas, no como número de tickets o compras.
3. **Descuentos:** Productos muestra `Descuento medio` y Promociones `Descuento promedio aplicado`; ambas medidas son promedios aritméticos de `descuento_pct` por línea, no un descuento monetario ponderado. El nombre y el catálogo del KPI deben dejarlo claro.
4. **Ventas por ciudad:** Panel y Tiendas presentan ventas por ciudad. Estos valores son ventas agregadas por ubicación, no necesariamente una comparación normalizada por tienda, superficie o cantidad de sucursales.
5. **Página inicial:** el orden de navegación empieza en Panel, pero `activePageName` apunta a Productos. Si se desea que el usuario aterrice primero en la vista ejecutiva, conviene cambiar la página activa a Panel.
6. **Especificación frente al contenido presente:** el contexto proponía seis tarjetas ejecutivas y una vista diagnóstica. La definición actual distribuye el diagnóstico en tres páginas temáticas y agrega visuales, pero conserva la tarjeta de ticket que contradice la limitación documentada de los datos.
7. **Indicador de promoción:** la medida de porcentaje con promoción se basa en ventas netas de líneas promocionadas frente a ventas netas totales. Representa proporción monetaria, no proporción de líneas o transacciones con campaña.
8. **Corte de crecimiento:** la medida `Crecimiento` usa el YTD y la última fecha de hecho bajo el contexto actual. No es necesariamente el KPI fijo enero-junio 2026 frente a enero-junio 2025 planteado en el contexto; el resultado puede variar con los filtros.
9. **Actualización de datos:** el informe apunta al modelo semántico, pero la fuente externa del modelo y el destino versionado del ETL deben alinearse para que refrescar el informe consuma la nueva ejecución. El informe por sí solo no resuelve esa integración.

## 8. Recomendaciones para cerrar la capa de presentación

1. Sustituir o renombrar las dos tarjetas de ticket y la medida DAX para que reflejen el grano real de línea.
2. Cambiar `activePageName` a Panel si la entrada ejecutiva es el recorrido esperado.
3. Mantener un catálogo de KPI con la misma definición y nombre que las medidas usadas por las tarjetas, matrices y gráficos.
4. Confirmar las interacciones cruzadas de los visuales y decidir si los segmentadores deben sincronizarse entre páginas.
5. Probar en Power BI Desktop que el informe abra, que el modelo resuelva todas las medidas y campos, y que las cuatro páginas se puedan recorrer sin visuales con error.
6. Probar un refresco real desde la fuente de SharePoint tras una publicación ETL, y verificar que el informe refleja la nueva versión.
7. Validar visualmente formatos, unidades, moneda, orden de meses, escalas, filtros y legibilidad en la vista de 1280 × 720.
8. Comparar ventas netas, margen y porcentaje de margen del informe con la salida Oro y el reporte de calidad de la misma ejecución.

## 9. Evidencia y límites de esta revisión

La descripción de páginas, conteos y campos se obtuvo de las definiciones JSON del informe y de su referencia al modelo semántico. El enlace de datos y las medidas se contrastaron con los TMDL y el código ETL versionados.

No se ejecutó Power BI Desktop o Service; no se verificó el refresco, credenciales de SharePoint, filtros efectivos, interacciones visuales, layout renderizado, desempeño ni coincidencia de cifras en pantalla. Las cifras de referencia del proyecto deben comprobarse contra los archivos Oro de la ejecución que se vaya a presentar.

## 10. Referencias del repositorio

- Proyecto del informe: `Oro.Report/definition.pbir`.
- Configuración y orden de páginas: `Oro.Report/definition/report.json` y `Oro.Report/definition/pages/pages.json`.
- Definición de páginas: `Oro.Report/definition/pages/<id>/page.json`.
- Consultas y formato de visuales: `Oro.Report/definition/pages/<id>/visuals/<visual>/visual.json`.
- Tema y fondo: `Oro.Report/StaticResources/RegisteredResources/oro.json` y `lienzo_oro.png`.
- Modelo semántico y medidas: `../Oro.SemanticModel/`.
- Generación de Excel Oro: `../andinos_etl/oro.py`.
- Empaquetado del artefacto Oro aprobado: `../andinos_etl/stages.py`.
- Publicación en SharePoint: `../andinos_etl/sharepoint.py`.

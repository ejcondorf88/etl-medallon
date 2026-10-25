"""CONTROLES DE CALIDAD: conciliaciones automáticas que prueban que los números son confiables."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

from .base import CapaMedallon
from .config import COLUMNAS_ESPERADAS, UMBRAL_COSTO_IMPUTADO


@dataclass
class ContextoCalidad:
    """Todo lo que un control puede necesitar mirar (se arma una vez y se comparte)."""
    bronce: dict[str, pd.DataFrame]
    plata: dict          # dict[str, ResultadoLimpieza]
    oro: dict[str, pd.DataFrame]


@dataclass
class ResultadoControl:
    control: str
    descripcion: str
    esperado: str
    obtenido: str
    estado: str          # OK, ADVERTENCIA o FALLO


class Control(ABC):
    """Un control = una pregunta con respuesta verificable."""
    nombre: str
    descripcion: str

    @abstractmethod
    def evaluar(self, ctx: ContextoCalidad) -> ResultadoControl: ...

    def _resultado(self, esperado, obtenido, ok: bool, estado_malo: str = "FALLO") -> ResultadoControl:
        return ResultadoControl(self.nombre, self.descripcion, str(esperado), str(obtenido),
                                "OK" if ok else estado_malo)


class ConciliacionFilas(Control):
    nombre = "C1 Conciliación de filas"
    descripcion = "Filas de bronce = filas de plata + rechazadas, y plata = hechos de oro"

    def evaluar(self, ctx):
        bronce = len(ctx.bronce["ventas"])
        plata = len(ctx.plata["ventas"].limpio)
        rechazadas = len(ctx.plata["ventas"].rechazado)
        oro = len(ctx.oro["fact_ventas"])
        ok = bronce == plata + rechazadas and plata == oro
        return self._resultado(f"{bronce} = {plata} + {rechazadas} = {oro} + rechazadas",
                               f"bronce {bronce} | plata {plata} | rechazadas {rechazadas} | oro {oro}", ok)


class ConciliacionMontos(Control):
    nombre = "C2 Conciliación de montos"
    descripcion = "Ventas netas del modelo = ventas netas recalculadas de forma independiente desde la bronce"

    def evaluar(self, ctx):
        # Recalculo independiente: solo desde el texto original, sin reutilizar nada de plata ni oro.
        b = ctx.bronce["ventas"].drop_duplicates(subset=COLUMNAS_ESPERADAS["ventas"])
        otras = ctx.plata["ventas"].rechazado
        otras = otras[otras["motivo_rechazo"] != "duplicado_exacto"]["_fila_origen"]
        b = b[~b["_fila_origen"].isin(otras)]
        num = lambda c: pd.to_numeric(b[c], errors="coerce")
        esperado = float((num("cantidad") * num("precio_unitario") * (1 - num("descuento_pct"))).sum())
        obtenido = float(ctx.oro["fact_ventas"]["importe_neto"].sum())
        return self._resultado(f"{esperado:,.2f}", f"{obtenido:,.2f}", abs(esperado - obtenido) < 0.01)


class IntegridadReferencial(Control):
    nombre = "C3 Integridad referencial"
    descripcion = "Toda llave del hecho existe en su dimensión (0 llaves huérfanas)"

    def evaluar(self, ctx):
        f = ctx.oro["fact_ventas"]
        relaciones = {"tienda_key": "dim_tienda", "producto_key": "dim_producto", "cliente_key": "dim_cliente",
                      "promocion_key": "dim_promocion", "fecha_key": "dim_fecha"}
        huerfanas = {llave: int((~f[llave].isin(ctx.oro[dim][llave])).sum()) for llave, dim in relaciones.items()}
        return self._resultado("0 huérfanas en las 5 relaciones", huerfanas, sum(huerfanas.values()) == 0)


class UnicidadLlaves(Control):
    nombre = "C4 Unicidad de llaves"
    descripcion = "Las llaves primarias de dimensiones y hechos no se repiten (relaciones 1:*)"

    def evaluar(self, ctx):
        llaves = {"dim_tienda": "tienda_key", "dim_producto": "producto_key", "dim_cliente": "cliente_key",
                  "dim_promocion": "promocion_key", "dim_fecha": "fecha_key", "fact_ventas": "venta_id"}
        repetidas = {t: int(ctx.oro[t][k].duplicated().sum()) for t, k in llaves.items()}
        return self._resultado("0 repetidas en las 6 tablas", repetidas, sum(repetidas.values()) == 0)


class CoherenciaDevoluciones(Control):
    nombre = "C5 Coherencia de devoluciones"
    descripcion = "Toda devolución tiene cantidad negativa y toda venta cantidad positiva"

    def evaluar(self, ctx):
        f = ctx.oro["fact_ventas"]
        malas = int(((f["es_devolucion"] == 1) & (f["cantidad"] >= 0)).sum()
                    + ((f["es_devolucion"] == 0) & (f["cantidad"] <= 0)).sum())
        return self._resultado("0 incoherentes", malas, malas == 0)


class PromocionesVigentes(Control):
    nombre = "C6 Promociones vigentes"
    descripcion = "Las ventas con promoción ocurren dentro de las fechas y la categoría de esa campaña"

    def evaluar(self, ctx):
        f, dp, dprod = ctx.oro["fact_ventas"], ctx.oro["dim_promocion"], ctx.oro["dim_producto"]
        x = (f[f["tiene_promocion"] == 1]
             .merge(dp, on="promocion_key").merge(dprod[["producto_key", "categoria"]], on="producto_key"))
        # Usamos fecha_key (AAAAMMDD) en lugar de fecha_hora (ya eliminada del hecho)
        dia = pd.to_datetime(x["fecha_key"].astype(str), format="%Y%m%d").dt.date
        fuera = int(((dia < x["fecha_inicio"]) | (dia > x["fecha_fin"])).sum())
        otra_cat = int((x["categoria"] != x["categoria_objetivo"]).sum())
        return self._resultado("0 fuera de fechas y 0 de otra categoría",
                               f"{fuera} fuera de fechas, {otra_cat} de otra categoría",
                               fuera == 0 and otra_cat == 0, estado_malo="ADVERTENCIA")


class CostoImputado(Control):
    nombre = "C7 Costos imputados"
    descripcion = "Parte de las líneas cuyo costo vacío se completó con el costo base del producto"

    def evaluar(self, ctx):
        f = ctx.oro["fact_ventas"]
        n, pct = int(f["costo_imputado"].sum()), f["costo_imputado"].mean()
        return self._resultado(f"<= {UMBRAL_COSTO_IMPUTADO:.0%}", f"{n} líneas ({pct:.2%})",
                               pct <= UMBRAL_COSTO_IMPUTADO, estado_malo="ADVERTENCIA")


class CapaCalidad(CapaMedallon):
    """Ejecuta todos los controles, guarda el reporte y dice si se puede publicar."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Para agregar un control nuevo basta con crear la clase y añadirla a esta lista.
        self.controles: list[Control] = [ConciliacionFilas(), ConciliacionMontos(), IntegridadReferencial(),
                                         UnicidadLlaves(), CoherenciaDevoluciones(), PromocionesVigentes(),
                                         CostoImputado()]

    def ejecutar(self, ctx: ContextoCalidad) -> pd.DataFrame:
        resultados = [c.evaluar(ctx) for c in self.controles]
        reporte = pd.DataFrame([vars(r) for r in resultados])
        self.almacen.escribir(reporte, self.settings.quality_dir / "reporte_calidad.csv")
        for r in resultados:
            self.log.info("Calidad | %-30s | %-11s | %s", r.control, r.estado, r.obtenido)
        return reporte

"""Orquestador: lee la bronce y genera plata -> oro -> calidad; falla si la calidad falla."""
from __future__ import annotations

import logging
import time

import pandas as pd

from .almacen import AlmacenCsv
from .bronce import CapaBronce
from .calidad import CapaCalidad, ContextoCalidad
from .config import Settings
from .excepciones import ErrorCalidad
from .oro import CapaOro
from .plata import CapaPlata


class PipelineMedallon:
    """Punto único de entrada del proceso. Inyecta las mismas dependencias a todas las capas."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        almacen = AlmacenCsv()
        self.bronce = CapaBronce(settings, almacen)
        self.plata = CapaPlata(settings, almacen)
        self.oro = CapaOro(settings, almacen)
        self.calidad = CapaCalidad(settings, almacen)
        self.log = logging.getLogger(self.__class__.__name__)

    def ejecutar(self) -> pd.DataFrame:
        inicio = time.perf_counter()
        self.log.info("Inicio del pipeline | carpeta de datos: %s", self.settings.data_dir.resolve())

        datos_bronce = self.bronce.ejecutar()                    # 1) leer la bronce (solo lectura)
        resultados_plata = self.plata.ejecutar(datos_bronce)     # 2) limpieza y validación
        limpias = {t: r.limpio for t, r in resultados_plata.items()}
        datos_oro = self.oro.ejecutar(limpias)                   # 3) modelo en estrella

        # 4) los controles deciden si lo publicado es confiable
        reporte = self.calidad.ejecutar(ContextoCalidad(datos_bronce, resultados_plata, datos_oro))
        if (reporte["estado"] == "FALLO").any():
            raise ErrorCalidad("Fallaron controles de calidad críticos; revise calidad/reporte_calidad.csv")

        self.log.info("Pipeline terminado en %.1f s", time.perf_counter() - inicio)
        return reporte

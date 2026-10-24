"""CAPA BRONCE: los datos originales, intactos. Esta clase solo los LEE y los valida; nunca los modifica."""
from __future__ import annotations

import pandas as pd

from .base import CapaMedallon
from .config import COLUMNAS_ESPERADAS, TABLAS
from .excepciones import ErrorEsquema


class CapaBronce(CapaMedallon):
    """Lee la carpeta `data/bronce`. Regla de oro: la bronce es de solo lectura (fuente de verdad)."""

    def ejecutar(self) -> dict[str, pd.DataFrame]:
        resultado: dict[str, pd.DataFrame] = {}

        for tabla in TABLAS:
            ruta = self.settings.archivo_bronce(tabla)

            # Paso 1: leer todo como texto para no perder información (ceros a la izquierda, vacíos).
            df = self.almacen.leer(ruta)

            # Paso 2: verificar el contrato de datos; si falta una columna, se detiene todo.
            self._validar_esquema(tabla, df)

            # Paso 3: anotar en memoria la fila de origen (trazabilidad hasta el archivo original).
            #         Solo en memoria: el archivo de bronce no se toca.
            df = df.assign(_fila_origen=range(2, len(df) + 2))    # la fila 1 es el encabezado

            self.log.info("Bronce | %-11s | %6d filas | %s", tabla, len(df), ruta.name)
            resultado[tabla] = df

        return resultado

    @staticmethod
    def _validar_esquema(tabla: str, df: pd.DataFrame) -> None:
        """Falla de inmediato si faltan columnas obligatorias (las extra se toleran)."""
        faltantes = [c for c in COLUMNAS_ESPERADAS[tabla] if c not in df.columns]
        if faltantes:
            raise ErrorEsquema(f"{tabla}: faltan las columnas {faltantes}")

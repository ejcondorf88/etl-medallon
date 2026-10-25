"""CAPA BRONCE: los datos originales, intactos. Esta clase solo los LEE y los valida; nunca los modifica."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import CapaMedallon
from .config import COLUMNAS_ESPERADAS, TABLAS
from .excepciones import ErrorEsquema


class CapaBronce(CapaMedallon):
    """Lee la carpeta `data/bronce`. Regla de oro: la bronce es de solo lectura (fuente de verdad)."""

    def ejecutar(self) -> dict[str, pd.DataFrame]:
        resultado: dict[str, pd.DataFrame] = {}
        lotes_por_tabla: dict[str, list[Path]] = {tabla: [] for tabla in TABLAS}
        carpeta_lotes = self.settings.bronze_dir / "lotes"
        if carpeta_lotes.exists():
            for archivo in sorted(carpeta_lotes.rglob("*.csv")):
                relativa = archivo.relative_to(carpeta_lotes)
                if len(relativa.parts) != 2 or archivo.stem not in TABLAS:
                    raise ErrorEsquema(
                        f"Archivo CSV de lote no reconocido: {relativa}. "
                        "Use lotes/<nombre-lote>/<tabla>.csv"
                    )
                lotes_por_tabla[archivo.stem].append(archivo)

        for tabla in TABLAS:
            fuentes = [self.settings.archivo_bronce(tabla)]
            fuentes.extend(lotes_por_tabla[tabla])

            partes: list[pd.DataFrame] = []
            siguiente_fila = 2
            for ruta in fuentes:
                # Leer como texto preserva identificadores, incluidos ceros a la izquierda.
                df = self.almacen.leer(ruta)
                self._validar_esquema(tabla, df)
                df = df[COLUMNAS_ESPERADAS[tabla]].copy()
                df = df.assign(_fila_origen=range(siguiente_fila, siguiente_fila + len(df)))
                siguiente_fila += len(df)
                partes.append(df)
                self.log.info("Bronce | %-11s | %6d filas | %s", tabla, len(df), ruta)

            resultado[tabla] = pd.concat(partes, ignore_index=True)

        return resultado

    @staticmethod
    def _validar_esquema(tabla: str, df: pd.DataFrame) -> None:
        """Falla de inmediato si faltan columnas obligatorias (las extra se toleran)."""
        faltantes = [c for c in COLUMNAS_ESPERADAS[tabla] if c not in df.columns]
        if faltantes:
            raise ErrorEsquema(f"{tabla}: faltan las columnas {faltantes}")

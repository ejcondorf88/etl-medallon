"""Punto de entrada. Con la carpeta data/bronce lista, basta con ejecutar:

    python main.py

y se generan data/plata (limpia), data/oro (modelo en estrella para Power BI) y data/calidad.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from andinos_etl.config import Settings
from andinos_etl.excepciones import ErrorETL
from andinos_etl.pipeline import PipelineMedallon
from andinos_etl.registro import configurar_logging


def leer_argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL medallón de Supermercados Andinos (bronce -> plata -> oro)")
    p.add_argument("--data-dir", type=Path, default=Path("data"),
                   help="carpeta que contiene bronce/ (por defecto: ./data)")
    return p.parse_args()


def main() -> int:
    args = leer_argumentos()
    settings = Settings(data_dir=args.data_dir)
    configurar_logging(settings.log_dir)
    try:
        PipelineMedallon(settings).ejecutar()
    except (ErrorETL, FileNotFoundError) as error:               # fallos esperados: mensaje claro
        logging.getLogger("main").error("El pipeline se detuvo: %s", error)
        return 1
    return 0                                                     # código 0 = todo bien


if __name__ == "__main__":
    sys.exit(main())

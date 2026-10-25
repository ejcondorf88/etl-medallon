from pathlib import Path

import pandas as pd
import pytest

from andinos_etl.bronce import CapaBronce
from andinos_etl.config import COLUMNAS_ESPERADAS, Settings
from andinos_etl.excepciones import ErrorEsquema


def crear_bronze(data_dir: Path) -> None:
    bronze = data_dir / "bronce"
    bronze.mkdir(parents=True)
    for tabla, columnas in COLUMNAS_ESPERADAS.items():
        fila = {columna: "valor" for columna in columnas}
        if tabla == "ventas":
            fila["cantidad"] = "1"
            fila["precio_unitario"] = "5.00"
            fila["descuento_pct"] = "0.00"
            fila["costo_unitario"] = "2.00"
        pd.DataFrame([fila]).to_csv(bronze / f"{tabla}.csv", index=False, encoding="utf-8-sig")


def test_bronze_lee_las_cinco_tablas_y_anota_lineaje(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    crear_bronze(settings.data_dir)

    resultado = CapaBronce(settings).ejecutar()

    assert set(resultado) == set(COLUMNAS_ESPERADAS)
    assert all("_fila_origen" in df.columns for df in resultado.values())
    assert all(df["_fila_origen"].tolist() == [2] for df in resultado.values())


def test_bronze_falla_si_falta_una_columna_del_contrato(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    crear_bronze(settings.data_dir)
    ruta = settings.archivo_bronce("ventas")
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.drop(columns=["fecha_hora"]).to_csv(ruta, index=False, encoding="utf-8-sig")

    with pytest.raises(ErrorEsquema, match="fecha_hora"):
        CapaBronce(settings).ejecutar()


def test_bronce_no_modifica_los_archivos_de_origen(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    crear_bronze(settings.data_dir)
    ruta = settings.archivo_bronce("ventas")
    contenido_previo = ruta.read_bytes()

    CapaBronce(settings).ejecutar()

    assert ruta.read_bytes() == contenido_previo

# -*- coding: utf-8 -*-
"""Genera datos/tarifas.xlsx, la planilla que edita el operador.

No sobreescribe una planilla existente salvo que se pase --forzar.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "datos" / "tarifas.xlsx"

COLUMNAS = [
    ("ORIGEN", 22, "Ciudad o terminal de origen. Obligatorio."),
    ("DESTINO", 22, "Ciudad o terminal de destino. Obligatorio."),
    ("TAMANO", 10, "20 o 40. Obligatorio."),
    ("TIPO", 14, "DRY / HC / REEFER / OPEN TOP / FLAT RACK / TANK. Obligatorio."),
    ("TARIFA", 12, "Importe numerico, sin simbolo de moneda. Obligatorio."),
    ("MONEDA", 10, "USD o ARS. Obligatorio."),
    ("TRANSPORTISTA", 22, "Opcional."),
    ("VIGENCIA DESDE", 16, "Opcional. Formato fecha."),
    ("VIGENCIA HASTA", 16, "Opcional. Vacio = sin vencimiento."),
    ("OBSERVACIONES", 40, "Opcional. Se muestra en el detalle de la tarifa."),
]

TIPOS = ["DRY", "HC", "REEFER", "OPEN TOP", "FLAT RACK", "TANK"]

EJEMPLOS = [
    ("MENDOZA", "BUENOS AIRES", 20, "DRY", 1450, "USD", "TRANSPORTES CUYO", None, None, "Incluye 48 h de estadia"),
    ("MENDOZA", "BUENOS AIRES", 40, "DRY", 1780, "USD", "TRANSPORTES CUYO", None, None, "Incluye 48 h de estadia"),
    ("MENDOZA", "BUENOS AIRES", 40, "HC", 1820, "USD", "TRANSPORTES CUYO", None, None, ""),
    ("MENDOZA", "BUENOS AIRES", 40, "REEFER", 2350, "USD", "FRIO ANDINO", None, None, "Requiere generador propio"),
    ("MENDOZA", "ZARATE", 20, "DRY", 1520, "USD", "TRANSPORTES CUYO", None, None, ""),
    ("MENDOZA", "ZARATE", 40, "DRY", 1850, "USD", "TRANSPORTES CUYO", None, None, ""),
    ("MENDOZA", "ROSARIO", 20, "DRY", 1280, "USD", "LOGISTICA DEL SUR", None, None, ""),
    ("MENDOZA", "ROSARIO", 40, "DRY", 1560, "USD", "LOGISTICA DEL SUR", None, None, ""),
    ("MENDOZA", "SAN ANTONIO (CHILE)", 20, "DRY", 1650, "USD", "ANDES CARGO", None, None, "Cruce Cristo Redentor sujeto a paso habilitado"),
    ("MENDOZA", "SAN ANTONIO (CHILE)", 40, "DRY", 1980, "USD", "ANDES CARGO", None, None, "Cruce Cristo Redentor sujeto a paso habilitado"),
    ("MENDOZA", "VALPARAISO (CHILE)", 40, "DRY", 2050, "USD", "ANDES CARGO", None, None, ""),
    ("MENDOZA", "VALPARAISO (CHILE)", 40, "REEFER", 2680, "USD", "FRIO ANDINO", None, None, ""),
    ("LUJAN DE CUYO", "BUENOS AIRES", 20, "TANK", 2100, "USD", "QUIMICA TRANSPORTE", None, None, "Carga IMO, documentacion especial"),
    ("SAN JUAN", "BUENOS AIRES", 40, "DRY", 1920, "USD", "LOGISTICA DEL SUR", None, None, ""),
    ("SAN RAFAEL", "BUENOS AIRES", 40, "DRY", 1890, "USD", "TRANSPORTES CUYO", None, None, ""),
    ("MENDOZA", "CORDOBA", 40, "DRY", 1180, "ARS", "LOGISTICA DEL SUR", None, None, "Tarifa en pesos por pedido del cliente"),
]

# La hoja CONFIG queda solo como referencia: publicar.py lee la configuracion
# de config.txt. La CLAVE_ACCESO no se escribe aca a proposito -ni como
# ejemplo-, porque esta planilla va a un recurso compartido que ve toda la
# oficina y cualquier clave que aparezca ahi se toma por buena.
CONFIG = [
    ("TITULO", "Tarifas Transporte Terrestre", "Solo informativo: el valor que vale esta en config.txt."),
    ("EMPRESA", "MARBLAU", "Solo informativo: el valor que vale esta en config.txt."),
]

AZUL = "1F3A5F"
GRIS = "F2F4F7"


def encabezado(ws, nombres, ancho_por_nombre):
    for i, nombre in enumerate(nombres, start=1):
        c = ws.cell(row=1, column=i, value=nombre)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = ancho_por_nombre[nombre]
    ws.row_dimensions[1].height = 24
    ws.freeze_panes = "A2"


def main():
    forzar = "--forzar" in sys.argv
    if DESTINO.exists() and not forzar:
        print(f"Ya existe {DESTINO}. No se toca (use --forzar para regenerarla).")
        return 0

    wb = Workbook()

    ws = wb.active
    ws.title = "TARIFAS"
    anchos = {n: a for n, a, _ in COLUMNAS}
    encabezado(ws, [n for n, _, _ in COLUMNAS], anchos)

    for fila in EJEMPLOS:
        ws.append(list(fila))

    ultima = ws.max_row
    for r in range(2, ultima + 1):
        ws.cell(row=r, column=5).number_format = "#,##0.00"
        ws.cell(row=r, column=8).number_format = "DD/MM/YYYY"
        ws.cell(row=r, column=9).number_format = "DD/MM/YYYY"
        ws.cell(row=r, column=3).alignment = Alignment(horizontal="center")

    tope = ultima + 400
    dv_tam = DataValidation(type="list", formula1='"20,40"', allow_blank=True)
    dv_tipo = DataValidation(type="list", formula1='"%s"' % ",".join(TIPOS), allow_blank=True)
    dv_mon = DataValidation(type="list", formula1='"USD,ARS"', allow_blank=True)
    for dv, col in ((dv_tam, "C"), (dv_tipo, "D"), (dv_mon, "F")):
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{tope}")

    wsc = wb.create_sheet("CONFIG")
    encabezado(wsc, ["CLAVE", "VALOR", "PARA QUE SIRVE"], {"CLAVE": 22, "VALOR": 34, "PARA QUE SIRVE": 62})
    for clave, valor, ayuda in CONFIG:
        wsc.append([clave, valor, ayuda])
    for r in range(2, wsc.max_row + 1):
        wsc.cell(row=r, column=1).font = Font(bold=True)
        wsc.cell(row=r, column=3).alignment = Alignment(wrap_text=True, vertical="top")

    wsi = wb.create_sheet("INSTRUCCIONES")
    wsi.column_dimensions["A"].width = 110
    texto = [
        ("COMO ACTUALIZAR LAS TARIFAS", True),
        ("", False),
        ("1. Edite la hoja TARIFAS: agregue, modifique o borre filas.", False),
        ("2. Guarde este archivo (Ctrl+S) y cierrelo.", False),
        ("3. Haga doble clic en PUBLICAR.bat, en la carpeta del proyecto.", False),
        ("4. Los celulares ven las tarifas nuevas al abrir la app, sin reinstalar nada.", False),
        ("", False),
        ("REGLAS DE LA HOJA TARIFAS", True),
        ("", False),
        ("- No cambie los nombres ni el orden de las columnas de la fila 1.", False),
        ("- ORIGEN, DESTINO, TAMANO, TIPO, TARIFA y MONEDA son obligatorios.", False),
        ("- TARIFA va como numero puro: 1450, no 'U$S 1.450'.", False),
        ("- TAMANO solo acepta 20 o 40. TIPO y MONEDA se eligen de la lista.", False),
        ("- Escriba el mismo origen siempre igual; el script ignora mayusculas y acentos.", False),
        ("- Una fila con VIGENCIA HASTA vencida se publica pero la app la marca como vencida.", False),
        ("- Si repite la misma combinacion origen+destino+tamano+tipo, el script avisa.", False),
        ("", False),
        ("CLAVE DE ACCESO", True),
        ("", False),
        ("- NO esta en esta planilla: esta en config.txt, en la carpeta del proyecto.", False),
        ("- Se saco de aca a proposito, porque esta planilla la ve toda la oficina.", False),
        ("- Las tarifas se publican cifradas con esa clave: sin la clave el archivo no se lee.", False),
        ("- Si la cambia, los usuarios tienen que escribir la clave nueva una sola vez.", False),
    ]
    for i, (linea, negrita) in enumerate(texto, start=1):
        c = wsi.cell(row=i, column=1, value=linea)
        if negrita:
            c.font = Font(bold=True, size=12, color=AZUL)
        else:
            c.font = Font(size=11)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(DESTINO)
    print(f"Plantilla creada: {DESTINO}")
    print(f"Filas de ejemplo: {len(EJEMPLOS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

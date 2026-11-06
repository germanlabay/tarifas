# -*- coding: utf-8 -*-
"""Lee datos/tarifas.xlsx, lo valida, lo cifra y lo deja publicable en app/datos/.

Uso:
    publicar.py            valida y genera app/datos/tarifas.json
    publicar.py --git      ademas hace commit y push si hay repo con remoto
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from openpyxl import load_workbook

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "datos" / "tarifas.json"
HUELLA = RAIZ / "datos" / ".huella"
CONFIG_RUTA = RAIZ / "planilla.txt"
POR_DEFECTO = RAIZ / "datos" / "tarifas.xlsx"


def ruta_planilla():
    """De donde se lee el Excel: argumento, planilla.txt, o la copia local.

    La planilla vive en un recurso compartido para que la mantenga el operador
    desde su propia PC, asi que la ruta es configurable y no esta en el codigo.
    """
    for a in sys.argv[1:]:
        if a.lower().endswith((".xlsx", ".xlsm")):
            return Path(a)
    if CONFIG_RUTA.exists():
        for linea in CONFIG_RUTA.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                return Path(linea)
    return POR_DEFECTO

ITERACIONES = 210_000
TIPOS_CONOCIDOS = {"DRY", "HC", "REEFER", "OPEN TOP", "FLAT RACK", "TANK"}
MONEDAS = {"USD", "ARS"}
TAMANOS = {"20", "40"}

REQUERIDAS = ["ORIGEN", "DESTINO", "TAMANO", "TIPO", "TARIFA", "MONEDA"]
OPCIONALES = ["TRANSPORTISTA", "VIGENCIA DESDE", "VIGENCIA HASTA", "OBSERVACIONES"]


def sin_acentos(t):
    t = unicodedata.normalize("NFKD", str(t))
    return "".join(c for c in t if not unicodedata.combining(c))


def norm_encabezado(t):
    t = sin_acentos(t or "").upper().strip()
    return re.sub(r"\s+", " ", t)


def limpiar(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return re.sub(r"\s+", " ", v).strip()
    return v


def texto_arriba(v):
    return re.sub(r"\s+", " ", str(v)).strip().upper() if v not in (None, "") else ""


def a_fecha(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    return "INVALIDA"


def a_numero(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v).strip())
    if not s:
        return None
    # 1.450,50 -> 1450.50 ; 1,450.50 -> 1450.50
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def leer_config(wb):
    cfg = {}
    if "CONFIG" not in wb.sheetnames:
        return cfg
    for fila in wb["CONFIG"].iter_rows(min_row=2, values_only=True):
        if not fila or not fila[0]:
            continue
        clave = norm_encabezado(fila[0]).replace(" ", "_")
        cfg[clave] = limpiar(fila[1]) if len(fila) > 1 else ""
    return cfg


def leer_tarifas(wb):
    if "TARIFAS" not in wb.sheetnames:
        raise SystemExit("ERROR: el archivo no tiene una hoja llamada TARIFAS.")
    ws = wb["TARIFAS"]

    encabezados = [norm_encabezado(c) for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    indice = {n: encabezados.index(n) for n in REQUERIDAS + OPCIONALES if n in encabezados}

    faltan = [n for n in REQUERIDAS if n not in indice]
    if faltan:
        raise SystemExit(
            "ERROR: faltan columnas obligatorias en la hoja TARIFAS: "
            + ", ".join(faltan)
            + "\nEncabezados encontrados: "
            + ", ".join(h for h in encabezados if h)
        )

    def celda(fila, nombre):
        i = indice.get(nombre)
        return fila[i] if i is not None and i < len(fila) else None

    hoy = date.today()
    tarifas, errores, avisos = [], [], []
    vistos = {}

    for nro, fila in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not fila or all(c in (None, "") for c in fila):
            continue

        origen = texto_arriba(celda(fila, "ORIGEN"))
        destino = texto_arriba(celda(fila, "DESTINO"))
        tam_bruto = celda(fila, "TAMANO")
        tipo = texto_arriba(celda(fila, "TIPO"))
        tarifa = a_numero(celda(fila, "TARIFA"))
        moneda = texto_arriba(celda(fila, "MONEDA"))

        tamano = ""
        if tam_bruto not in (None, ""):
            n = a_numero(tam_bruto)
            tamano = str(int(n)) if n is not None and n == int(n) else texto_arriba(tam_bruto)

        problemas = []
        if not origen:
            problemas.append("ORIGEN vacio")
        if not destino:
            problemas.append("DESTINO vacio")
        if tamano not in TAMANOS:
            problemas.append("TAMANO '%s' no es 20 ni 40" % limpiar(tam_bruto))
        if not tipo:
            problemas.append("TIPO vacio")
        if tarifa is None:
            problemas.append("TARIFA '%s' no es un numero" % limpiar(celda(fila, "TARIFA")))
        elif tarifa <= 0:
            problemas.append("TARIFA debe ser mayor que cero")
        if moneda not in MONEDAS:
            problemas.append("MONEDA '%s' no es USD ni ARS" % moneda)

        if problemas:
            errores.append("  fila %d: %s" % (nro, "; ".join(problemas)))
            continue

        if tipo not in TIPOS_CONOCIDOS:
            avisos.append("  fila %d: TIPO '%s' no esta en la lista habitual, se publica igual" % (nro, tipo))

        desde = a_fecha(celda(fila, "VIGENCIA DESDE"))
        hasta = a_fecha(celda(fila, "VIGENCIA HASTA"))
        if desde == "INVALIDA":
            avisos.append("  fila %d: VIGENCIA DESDE no se entiende como fecha, se ignora" % nro)
            desde = None
        if hasta == "INVALIDA":
            avisos.append("  fila %d: VIGENCIA HASTA no se entiende como fecha, se ignora" % nro)
            hasta = None

        vencida = bool(hasta and hasta < hoy)
        if vencida:
            avisos.append("  fila %d: vigencia vencida el %s, la app la marca como vencida" % (nro, hasta.strftime("%d/%m/%Y")))

        clave = (origen, destino, tamano, tipo)
        if clave in vistos:
            avisos.append(
                "  fila %d: repite %s > %s %s pies %s (ya estaba en la fila %d)"
                % (nro, origen, destino, tamano, tipo, vistos[clave])
            )
        vistos[clave] = nro

        tarifas.append(
            {
                "id": len(tarifas) + 1,
                "o": origen,
                "d": destino,
                "tam": tamano,
                "tipo": tipo,
                "tarifa": round(tarifa, 2),
                "moneda": moneda,
                "transportista": limpiar(celda(fila, "TRANSPORTISTA")) or "",
                "desde": desde.isoformat() if isinstance(desde, date) else None,
                "hasta": hasta.isoformat() if isinstance(hasta, date) else None,
                "obs": limpiar(celda(fila, "OBSERVACIONES")) or "",
                "vencida": vencida,
                "b": sin_acentos("%s %s %s %s" % (origen, destino, tipo, tamano)).upper(),
            }
        )

    return tarifas, errores, avisos


def cifrar(payload_bytes, clave):
    sal = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=ITERACIONES)
    llave = kdf.derive(clave.encode("utf-8"))
    iv = os.urandom(12)
    datos = AESGCM(llave).encrypt(iv, payload_bytes, None)

    def b64(x):
        return base64.b64encode(x).decode("ascii")

    return {
        "kdf": {"alg": "PBKDF2-SHA256", "iteraciones": ITERACIONES, "sal": b64(sal)},
        "cifrado": {"alg": "AES-256-GCM", "iv": b64(iv), "datos": b64(datos)},
    }


def git_publicar():
    def git(*args):
        return subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True)

    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        print("\nAviso: la carpeta no es un repositorio git, no se subio nada.")
        print("Vea PUBLICAR-EN-INTERNET.md para configurar el hosting una sola vez.")
        return False
    if not git("remote", "get-url", "origin").stdout.strip():
        print("\nAviso: el repositorio no tiene remoto 'origin', no se subio nada.")
        return False

    git("add", "docs/datos/tarifas.json")
    if git("diff", "--cached", "--quiet").returncode == 0:
        print("\nLas tarifas publicadas no cambiaron, no hay nada que subir.")
        return True

    sello = datetime.now().strftime("%d/%m/%Y %H:%M")
    hecho = git("commit", "-m", "Tarifas actualizadas " + sello)
    if hecho.returncode != 0:
        print("\nERROR al hacer commit:\n" + (hecho.stderr or hecho.stdout))
        return False
    empuje = git("push")
    if empuje.returncode != 0:
        print("\nERROR al hacer push:\n" + (empuje.stderr or empuje.stdout))
        return False
    print("\nPublicado en internet. Los celulares lo ven al abrir la app.")
    return True


def main():
    origen = ruta_planilla()
    try:
        existe = origen.exists()
    except OSError:
        existe = False

    if not existe:
        if str(origen).startswith(("\\\\", "//")):
            raise SystemExit(
                "ERROR: no se llega a la planilla en la red:\n"
                "  %s\n\n"
                "Revise que la PC que la comparte este encendida y conectada.\n"
                "La ruta configurada esta en %s" % (origen, CONFIG_RUTA)
            )
        raise SystemExit(
            "ERROR: no se encuentra la planilla:\n"
            "  %s\n\n"
            "Ejecute scripts/crear_plantilla.py para generarla, o indique la ruta\n"
            "correcta en %s" % (origen, CONFIG_RUTA)
        )

    try:
        wb = load_workbook(origen, data_only=True)
    except PermissionError:
        raise SystemExit(
            "ERROR: no se pudo leer la planilla:\n"
            "  %s\n\n"
            "Puede estar abierta con bloqueo exclusivo. Cierrela y reintente." % origen
        )
    cfg = leer_config(wb)
    clave = str(cfg.get("CLAVE_ACCESO", "") or "").strip()
    if not clave:
        raise SystemExit(
            "ERROR: la hoja CONFIG no tiene una CLAVE_ACCESO.\n"
            "Escriba una clave en la columna VALOR de la fila CLAVE_ACCESO."
        )
    if len(clave) < 4:
        raise SystemExit("ERROR: la CLAVE_ACCESO es demasiado corta, use al menos 4 caracteres.")

    tarifas, errores, avisos = leer_tarifas(wb)

    print("=" * 66)
    print(" PUBLICAR TARIFAS")
    print("=" * 66)
    print("Planilla      : %s" % origen)
    print("Filas validas : %d" % len(tarifas))

    if avisos:
        print("\nAvisos (%d):" % len(avisos))
        for a in avisos:
            print(a)

    if errores:
        print("\nERRORES (%d) - no se publico nada:" % len(errores))
        for e in errores:
            print(e)
        print("\nCorrija esas filas en el Excel, guarde y vuelva a publicar.")
        return 1

    if not tarifas:
        print("\nERROR: la hoja TARIFAS no tiene ninguna fila valida, no se publico nada.")
        return 1

    contenido = {
        "titulo": cfg.get("TITULO") or "Tarifas de Transporte",
        "empresa": cfg.get("EMPRESA") or "",
        "tarifas": tarifas,
    }

    # Cada cifrado usa sal e IV nuevos, asi que el archivo cambia aunque las
    # tarifas no. Para no generar commits vacios se compara una huella de lo
    # que importa -el contenido y la clave, sin el sello de tiempo, que cambia
    # siempre-. Se guarda junto al Excel, fuera del repositorio: depende de la
    # clave y no tiene por que publicarse.
    estable = json.dumps(contenido, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    huella = hashlib.sha256(clave.encode("utf-8") + b"|" + estable).hexdigest()
    anterior = HUELLA.read_text(encoding="utf-8").strip() if HUELLA.exists() else None

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    sin_cambios = anterior == huella and SALIDA.exists()

    if not sin_cambios:
        generado = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        crudo = json.dumps(dict(generado=generado, **contenido), ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
        sobre = {"formato": "marblau-tarifas-1", "generado": generado, "cantidad": len(tarifas)}
        sobre.update(cifrar(crudo, clave))
        SALIDA.write_text(json.dumps(sobre, ensure_ascii=False), encoding="utf-8")
        HUELLA.write_text(huella, encoding="utf-8")

    origenes = sorted({t["o"] for t in tarifas})
    destinos = sorted({t["d"] for t in tarifas})
    if sin_cambios:
        print("\nLas tarifas no cambiaron desde la ultima publicacion.")
        print("Se mantiene el archivo que ya estaba.")
    else:
        print("\nGenerado : %s" % SALIDA)
        print("Tamano   : %.1f KB (cifrado)" % (SALIDA.stat().st_size / 1024))
    print("Origenes : %d  |  Destinos: %d" % (len(origenes), len(destinos)))
    print("Sello    : %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))

    if "--git" in sys.argv:
        git_publicar()
    else:
        print("\n(Archivo generado localmente. Agregue --git para subirlo a internet.)")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

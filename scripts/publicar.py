# -*- coding: utf-8 -*-
"""Lee el tarifario, lo valida, lo cifra y lo deja publicable en docs/datos/.

Uso:
    publicar.py            genera docs/datos/tarifas.json
    publicar.py --git      ademas hace commit y push si hay repo con remoto
    publicar.py <archivo>  usa esa planilla en vez de la configurada
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import tarifario

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "datos" / "tarifas.json"
HUELLA = RAIZ / "datos" / ".huella"
CONFIG_PLANILLA = RAIZ / "planilla.txt"
CONFIG = RAIZ / "config.txt"

ITERACIONES = 210_000


def ruta_planilla():
    """De donde se lee el Excel: argumento, planilla.txt, o la copia local.

    La planilla vive en un recurso compartido para que la mantenga el operador
    desde su propia PC, asi que la ruta es configurable y no esta en el codigo.
    """
    for a in sys.argv[1:]:
        if a.lower().endswith((".xlsx", ".xlsm")):
            return Path(a)
    if CONFIG_PLANILLA.exists():
        for linea in CONFIG_PLANILLA.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#"):
                return Path(linea)
    return RAIZ / "datos" / "tarifas.xlsx"


def leer_config():
    """config.txt: CLAVE=VALOR por linea.

    La clave de acceso vive aca y no en el Excel, porque el Excel esta en un
    recurso compartido que ve toda la oficina. Este archivo no se versiona.
    """
    if not CONFIG.exists():
        raise SystemExit(
            "ERROR: falta el archivo de configuracion:\n  %s\n\n"
            "Tiene que tener al menos la linea:\n"
            "  CLAVE_ACCESO=la-clave-que-use-la-gente" % CONFIG
        )
    cfg = {}
    for linea in CONFIG.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        cfg[k.strip().upper()] = v.strip()
    return cfg


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
    cfg = leer_config()
    clave = cfg.get("CLAVE_ACCESO", "").strip()
    if not clave:
        raise SystemExit(
            "ERROR: %s no tiene una CLAVE_ACCESO.\n"
            "Agregue la linea:  CLAVE_ACCESO=la-clave" % CONFIG
        )
    if len(clave) < 4:
        raise SystemExit("ERROR: la CLAVE_ACCESO es demasiado corta, use al menos 4 caracteres.")

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
                "La ruta configurada esta en %s" % (origen, CONFIG_PLANILLA)
            )
        raise SystemExit(
            "ERROR: no se encuentra la planilla:\n  %s\n\n"
            "Indique la ruta correcta en %s" % (origen, CONFIG_PLANILLA)
        )

    try:
        datos, avisos, errores = tarifario.leer(origen, cfg.get("HOJA") or None)
    except PermissionError:
        raise SystemExit(
            "ERROR: no se pudo leer la planilla:\n  %s\n\n"
            "Puede estar abierta con bloqueo exclusivo. Cierrela y reintente." % origen
        )

    print("=" * 70)
    print(" PUBLICAR TARIFAS")
    print("=" * 70)
    print("Planilla : %s" % origen)
    if datos:
        print("Hoja     : %s" % datos["hoja"])

    if avisos:
        print("\nAvisos (%d):" % len(avisos))
        for a in avisos:
            print("  " + a)

    if errores:
        print("\nERRORES (%d) - no se publico nada:" % len(errores))
        for e in errores:
            print("  " + e)
        print("\nCorrija la planilla y vuelva a publicar.")
        return 1

    contenido = {
        "titulo": cfg.get("TITULO") or "Tarifas de Transporte",
        "empresa": cfg.get("EMPRESA") or "",
        "destino": datos["destino"],
        "moneda": datos["moneda"],
        "hoja": datos["hoja"],
        "zonas": datos["zonas"],
        "tamanos": datos["tamanos"],
        "modalidades": datos["modalidades"],
        "transportistas": datos["transportistas"],
        "tarifas": datos["tarifas"],
    }

    # Cada cifrado usa sal e IV nuevos, asi que el archivo cambia aunque las
    # tarifas no. Para no generar commits vacios se compara una huella de lo
    # que importa -el contenido y la clave, sin el sello de tiempo-. Se guarda
    # fuera del repositorio: depende de la clave.
    estable = json.dumps(contenido, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    huella = hashlib.sha256(clave.encode("utf-8") + b"|" + estable).hexdigest()
    anterior = HUELLA.read_text(encoding="utf-8").strip() if HUELLA.exists() else None

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    HUELLA.parent.mkdir(parents=True, exist_ok=True)
    sin_cambios = anterior == huella and SALIDA.exists()

    if not sin_cambios:
        generado = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        crudo = json.dumps(dict(generado=generado, **contenido), ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
        sobre = {"formato": "marblau-tarifas-2", "generado": generado,
                 "cantidad": len(datos["tarifas"])}
        sobre.update(cifrar(crudo, clave))
        SALIDA.write_text(json.dumps(sobre, ensure_ascii=False), encoding="utf-8")
        HUELLA.write_text(huella, encoding="utf-8")

    print("\nTarifas  : %d" % len(datos["tarifas"]))
    print("Destino  : %s   |   Moneda: %s" % (datos["destino"], datos["moneda"]))
    print("Zonas    : %d  (%s)" % (len(datos["zonas"]), ", ".join(datos["zonas"])))
    print("Empresas : %d  (%s)" % (len(datos["transportistas"]),
                                   ", ".join(sorted(datos["transportistas"]))))
    if sin_cambios:
        print("\nLas tarifas no cambiaron desde la ultima publicacion.")
        print("Se mantiene el archivo que ya estaba.")
    else:
        print("\nGenerado : %s" % SALIDA)
        print("Tamano   : %.1f KB (cifrado)" % (SALIDA.stat().st_size / 1024))
    print("Sello    : %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))

    if "--git" in sys.argv:
        git_publicar()
    else:
        print("\n(Archivo generado localmente. Agregue --git para subirlo a internet.)")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

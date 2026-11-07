# -*- coding: utf-8 -*-
"""Corre el publicador sin ventana, para la tarea programada.

La diferencia con PUBLICAR.bat no es solo la ventana: ahi hay alguien mirando
la pantalla, y aca no hay nadie. Entonces:

- No anota las corridas en las que no cambio nada. Si se anotaran, el registro
  serian cien lineas por dia diciendo "sin cambios" y nadie encontraria el
  error cuando pase.
- Si falla, lo deja escrito igual, con la salida completa.
- Siempre refresca estado.txt, aunque no haya cambiado nada, asi se puede
  distinguir "no hay tarifas nuevas" de "la tarea dejo de correr".
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYTHON = RAIZ / "venv" / "Scripts" / "python.exe"
PUBLICAR = RAIZ / "scripts" / "publicar.py"
REGISTRO = RAIZ / "datos" / "publicacion.log"
ESTADO = RAIZ / "datos" / "estado.txt"

# Un registro que crece sin limite termina siendo un archivo de 200 MB que
# nadie abre. Se recorta por la mitad cuando pasa de esto.
TOPE_BYTES = 200_000


def recortar():
    if REGISTRO.exists() and REGISTRO.stat().st_size > TOPE_BYTES:
        lineas = REGISTRO.read_text(encoding="utf-8", errors="replace").splitlines()
        REGISTRO.write_text(
            "(registro recortado)\n" + "\n".join(lineas[len(lineas) // 2:]) + "\n",
            encoding="utf-8",
        )


def anotar(sello, titulo, salida):
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    recortar()
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write("\n%s  %s\n" % (sello, titulo))
        for linea in salida.rstrip().splitlines():
            f.write("    %s\n" % linea)


def main():
    sello = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        r = subprocess.run(
            [str(PYTHON), str(PUBLICAR), "--git"],
            cwd=str(RAIZ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        salida = (r.stdout or "") + (r.stderr or "")
        codigo = r.returncode
    except subprocess.TimeoutExpired:
        salida = "El publicador tardo mas de 5 minutos y se corto."
        codigo = -1
    except Exception as e:  # noqa: BLE001 - nadie esta mirando, hay que anotarlo
        salida = "No se pudo ejecutar el publicador: %r" % e
        codigo = -1

    fallo = codigo != 0 or "ERROR" in salida
    sin_cambios = "no cambiaron" in salida or "no hay nada que subir" in salida

    if fallo:
        estado = "FALLO"
        anotar(sello, "FALLO (codigo %s)" % codigo, salida)
    elif sin_cambios:
        estado = "sin cambios"
    else:
        estado = "publicado"
        anotar(sello, "publicado", salida)

    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(
        "Ultima corrida automatica: %s\nResultado: %s\n\n"
        "Si esta fecha quedo vieja, la tarea programada no esta corriendo:\n"
        "puede estar cerrada la sesion de Windows en esta PC.\n"
        "El detalle de las publicaciones y los errores esta en publicacion.log\n"
        % (sello, estado),
        encoding="utf-8",
    )
    return 1 if fallo else 0


if __name__ == "__main__":
    sys.exit(main())

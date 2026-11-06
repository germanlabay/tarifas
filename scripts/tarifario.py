# -*- coding: utf-8 -*-
"""Lee el tarifario de transporte terrestre, que viene como matriz cruzada.

La hoja no es una lista de tarifas sino un bloque por transportista:

    fila i   | B=<TRANSPORTISTA> | C=ITEMS | E=<ZONA1> ... H=<ZONA2> ...
    fila i+1 |                   |         | E=20  F=40  G=40 HCR  ...
    fila i+2 |                   | C=OW    | <tarifas de ida>
    fila i+3 |                   | C=RT    | <tarifas de ida y vuelta>
    fila i+4 |                   | C=GENSET   | D=<recargo>
    fila i+5 |                   | C=CDA      | D=<recargo> | F=FECHA COTIZACION ...
    fila i+6 |                   | C=VACIO 20 | D=<recargo> | F=ATA ...
    fila i+7 |                   | C=VACIO 40 | D=<recargo> | F=Empresa Chilena ...

Cada zona ocupa 3 columnas (20 / 40 / 40 HCR) y hay 8 zonas, de E a AB.

Se publica solo esta grilla. La seccion COTIZACIONES PUNTUALES del final de la
hoja queda afuera a propósito: mezcla unidades (contenedor, big bag, pallets,
tambores), monedas y notas en las mismas celdas, y normalizarla a ciegas haria
que la app muestre importes equivocados.
"""
import itertools
import re
import statistics
import unicodedata
from datetime import date, datetime

from openpyxl import load_workbook

# La grilla no declara moneda en ninguna celda. Los importes (1400 a 3200) solo
# cierran en dolares; en pesos serian absurdos. Se asume USD y se informa.
MONEDA = "USD"
DESTINO = "CHILE"

COL_TRANSPORTISTA = 1   # B
COL_ETIQUETA = 2        # C
COL_RECARGO = 3         # D
COL_PRIMERA_ZONA = 4    # E
COL_ULTIMA_ZONA = 28    # AB + 1

MODALIDADES = {"OW": "Ida", "RT": "Ida y vuelta"}
RECARGOS = ("GENSET", "CDA", "VACIO 20", "VACIO 40")


def sin_acentos(t):
    t = unicodedata.normalize("NFKD", str(t))
    return "".join(c for c in t if not unicodedata.combining(c))


def limpiar(v):
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def arriba(v):
    return sin_acentos(limpiar(v)).upper()


def numero(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if v is None:
        return None
    s = re.sub(r"[^\d,.\-]", "", str(v).strip())
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def elegir_hoja(wb, pedida=None):
    """La hoja vigente es 'TARIFARIO DESDE EL <fecha>'; se toma la mas nueva."""
    if pedida:
        if pedida not in wb.sheetnames:
            raise SystemExit(
                "ERROR: la planilla no tiene una hoja llamada '%s'.\nHojas: %s"
                % (pedida, ", ".join(wb.sheetnames))
            )
        return pedida

    candidatas = []
    for nombre in wb.sheetnames:
        m = re.search(r"DESDE\s+EL\s+(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", arriba(nombre))
        if m:
            d, mes, a = (int(x) for x in m.groups())
            a += 2000 if a < 100 else 0
            try:
                candidatas.append((date(a, mes, d), nombre))
            except ValueError:
                continue
    if candidatas:
        return max(candidatas)[1]

    for nombre in wb.sheetnames:
        if "TARIFARIO" in arriba(nombre):
            return nombre
    raise SystemExit(
        "ERROR: no se encontro una hoja de tarifario en la planilla.\nHojas: %s"
        % ", ".join(wb.sheetnames)
    )


def _valor_a_la_derecha(fila, desde):
    for j in range(desde + 1, len(fila)):
        if limpiar(fila[j]):
            return fila[j]
    return None


def _buscar_etiqueta(fila, texto):
    """Devuelve el valor que sigue a una etiqueta como 'ATA' o 'FECHA COTIZACION'."""
    objetivo = arriba(texto)
    for j, v in enumerate(fila):
        if arriba(v) == objetivo:
            return _valor_a_la_derecha(fila, j)
    return None


def _contacto(fila):
    """Los contactos van sueltos a la derecha: nombre, 'CEL', telefono, mail."""
    nombre = tel = mail = ""
    for j, v in enumerate(fila):
        s = limpiar(v)
        if not s:
            continue
        if "@" in s:
            mail = s
        elif arriba(s) == "CEL":
            sig = _valor_a_la_derecha(fila, j)
            tel = limpiar(sig)
        elif j >= 16 and not nombre and not re.search(r"\d{4}", s) and arriba(s) != "CEL":
            nombre = s
    if not (nombre or tel or mail):
        return None
    return {"nombre": nombre, "tel": tel, "mail": mail}


def _combinaciones_recargos(recargos):
    """Todas las sumas posibles de los recargos de un transportista.

    Devuelve {importe: 'GENSET + CDA'} para poder explicar el descarte.
    """
    items = [(k, v) for k, v in recargos.items() if v and v > 0]
    sumas = {}
    for n in range(1, len(items) + 1):
        for combo in itertools.combinations(items, n):
            total = round(sum(v for _, v in combo), 2)
            sumas.setdefault(total, " + ".join(k for k, _ in combo))
    return sumas


def _descartar_residuos(tarifas, transportistas):
    """Saca las celdas que son residuo de formula, no tarifas.

    Cuando el transportista no cotizo una zona, la celda igual trae la suma de
    sus propios recargos (GENSET + CDA, o el vacio). Publicar eso haria que la
    app lo muestre como el mas barato por lejos, que es el peor error posible
    en una app de cotizar.

    Se exige doble coincidencia para no descartar una tarifa real barata: que
    el importe sea exactamente una suma de recargos de ESE transportista, y que
    ademas quede por debajo de la mitad de la mediana de su grupo comparable.
    """
    grupos = {}
    for t in tarifas:
        grupos.setdefault((t["zona"], t["tam"], t["mod"]), []).append(t["tarifa"])
    medianas = {k: statistics.median(v) for k, v in grupos.items()}

    sumas_por_empresa = {
        nombre: _combinaciones_recargos(ficha.get("recargos", {}))
        for nombre, ficha in transportistas.items()
    }

    limpias, descartadas = [], []
    for t in tarifas:
        clave = (t["zona"], t["tam"], t["mod"])
        sumas = sumas_por_empresa.get(t["t"], {})
        explicacion = sumas.get(round(t["tarifa"], 2))
        if (explicacion
                and len(grupos[clave]) >= 3
                and t["tarifa"] < medianas[clave] * 0.5):
            descartadas.append(dict(t, explicacion=explicacion))
        else:
            limpias.append(t)
    return limpias, descartadas


def leer(ruta, hoja_pedida=None):
    """Devuelve (datos, avisos, errores)."""
    wb = load_workbook(ruta, data_only=True, read_only=True)
    try:
        hoja = elegir_hoja(wb, hoja_pedida)
        filas = [list(f) for f in wb[hoja].iter_rows(values_only=True)]
    finally:
        wb.close()

    avisos, errores = [], []
    tarifas, transportistas = [], {}
    # El orden de zonas y tamanos es el de la planilla (las zonas van de mas
    # cerca a mas lejos), que le dice mas al operador que el alfabetico.
    orden_zonas, orden_tam = [], []

    inicios = [i for i, f in enumerate(filas)
               if len(f) > COL_ETIQUETA and arriba(f[COL_ETIQUETA]) == "ITEMS"]
    if not inicios:
        errores.append("La hoja '%s' no tiene bloques de transportista (no se encontro 'ITEMS')." % hoja)
        return None, avisos, errores

    for i in inicios:
        fila_cab = filas[i]
        nombre = limpiar(fila_cab[COL_TRANSPORTISTA] if len(fila_cab) > COL_TRANSPORTISTA else "")
        if not nombre:
            avisos.append("fila %d: bloque sin nombre de transportista, se omite." % (i + 1))
            continue
        if nombre in transportistas:
            avisos.append("fila %d: '%s' aparece mas de una vez; se usa el primer bloque." % (i + 1, nombre))
            continue

        if i + 1 >= len(filas):
            avisos.append("fila %d: '%s' no tiene fila de tamanos, se omite." % (i + 1, nombre))
            continue
        fila_tam = filas[i + 1]

        # columna -> (zona, tamano)
        columnas = {}
        zona_actual = None
        for j in range(COL_PRIMERA_ZONA, min(COL_ULTIMA_ZONA, max(len(fila_cab), len(fila_tam)))):
            etiqueta_zona = limpiar(fila_cab[j]) if j < len(fila_cab) else ""
            if etiqueta_zona:
                zona_actual = etiqueta_zona
            tam = arriba(fila_tam[j]) if j < len(fila_tam) else ""
            if zona_actual and tam:
                columnas[j] = (zona_actual, tam.replace("´", "").replace("'", "").strip())

        if not columnas:
            avisos.append("fila %d: '%s' no tiene zonas reconocibles, se omite." % (i + 1, nombre))
            continue

        for j in sorted(columnas):
            zona, tam = columnas[j]
            if zona not in orden_zonas:
                orden_zonas.append(zona)
            if tam not in orden_tam:
                orden_tam.append(tam)

        # etiquetas de la columna C dentro del bloque
        etiquetas = {}
        for k in range(i + 1, min(i + 12, len(filas))):
            if k in inicios:
                break
            e = arriba(filas[k][COL_ETIQUETA]) if len(filas[k]) > COL_ETIQUETA else ""
            if e and e not in etiquetas:
                etiquetas[e] = k

        cuantas = 0
        for mod, mod_texto in MODALIDADES.items():
            k = etiquetas.get(mod)
            if k is None:
                avisos.append("fila %d: '%s' no tiene fila %s." % (i + 1, nombre, mod))
                continue
            fila = filas[k]
            for j, (zona, tam) in columnas.items():
                bruto = fila[j] if j < len(fila) else None
                if bruto is None or limpiar(bruto) == "":
                    continue
                v = numero(bruto)
                if v is None:
                    avisos.append("fila %d col %d: '%s' %s %s %s no es un numero, se omite."
                                  % (k + 1, j + 1, nombre, zona, tam, mod))
                    continue
                if v <= 0:
                    continue  # 0 = sin cotizar, no es una tarifa de cero
                tarifas.append({
                    "id": len(tarifas) + 1,
                    "t": nombre,
                    "zona": zona,
                    "tam": tam,
                    "mod": mod,
                    "tarifa": round(v, 2),
                    "b": arriba("%s %s %s %s" % (nombre, zona, tam, mod_texto)),
                })
                cuantas += 1

        if not cuantas:
            avisos.append("fila %d: '%s' no tiene ninguna tarifa cargada, se omite." % (i + 1, nombre))
            continue

        ficha = {"recargos": {}}
        for etq in RECARGOS:
            k = etiquetas.get(etq)
            if k is None:
                continue
            v = numero(filas[k][COL_RECARGO] if len(filas[k]) > COL_RECARGO else None)
            if v is not None and v > 0:
                ficha["recargos"][etq] = round(v, 2)

        contactos = []
        for etq, campo, clave in (("CDA", "FECHA COTIZACION", "fecha"),
                                  ("VACIO 20", "ATA", "ata"),
                                  ("VACIO 40", "Empresa Chilena", "chilena")):
            k = etiquetas.get(etq)
            if k is None:
                continue
            fila = filas[k]
            v = _buscar_etiqueta(fila, campo)
            if isinstance(v, datetime):
                ficha[clave] = v.date().isoformat()
            elif isinstance(v, date):
                ficha[clave] = v.isoformat()
            elif limpiar(v):
                ficha[clave] = limpiar(v)
            c = _contacto(fila)
            if c and c not in contactos:
                contactos.append(c)
        if contactos:
            ficha["contactos"] = contactos

        transportistas[nombre] = ficha

    if not tarifas:
        errores.append("No se pudo leer ninguna tarifa de la hoja '%s'." % hoja)
        return None, avisos, errores

    tarifas, descartadas = _descartar_residuos(tarifas, transportistas)
    for d in descartadas:
        avisos.append(
            "'%s' %s %s %s: %g no es un flete sino la suma de sus recargos (%s); "
            "se toma como no cotizado."
            % (d["t"], d["zona"], d["tam"], d["mod"], d["tarifa"], d["explicacion"])
        )

    if not tarifas:
        errores.append("Tras descartar residuos no quedo ninguna tarifa en la hoja '%s'." % hoja)
        return None, avisos, errores

    vivos = {t["t"] for t in tarifas}
    for nombre in [n for n in transportistas if n not in vivos]:
        del transportistas[nombre]

    for n, t in enumerate(tarifas, start=1):
        t["id"] = n

    con_datos = {t["zona"] for t in tarifas}
    tam_con_datos = {t["tam"] for t in tarifas}

    datos = {
        "hoja": hoja,
        "destino": DESTINO,
        "moneda": MONEDA,
        "zonas": [z for z in orden_zonas if z in con_datos],
        "tamanos": [t for t in orden_tam if t in tam_con_datos],
        "modalidades": [{"id": k, "texto": v} for k, v in MODALIDADES.items()],
        "transportistas": transportistas,
        "tarifas": tarifas,
    }
    return datos, avisos, errores

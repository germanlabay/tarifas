# Tarifas de Transporte

App para celular que consulta tarifas de transporte terrestre por **origen,
destino, tipo y tamaño de contenedor**. Los datos salen de una planilla Excel
que mantiene un operador; los celulares se actualizan solos.

---

## Las dos personas que usan esto

**El operador** edita `datos\tarifas.xlsx` y hace doble clic en `PUBLICAR.bat`.
Nada más.

**Los usuarios** abren la app en el celular, escriben la clave una sola vez y
consultan. No instalan nada desde una tienda ni actualizan nada a mano.

---

## Cómo se actualiza una tarifa

1. Abrir la planilla: **`\\PC-02\Compartido\tarifas.xlsx`**.
2. Cambiar, agregar o borrar filas en la hoja **TARIFAS**.
3. **Guardar** el Excel (con guardar alcanza; no hace falta cerrarlo).
4. Doble clic en **`PUBLICAR.bat`**.

La ventana negra muestra el resultado:

- **Filas validas: N** y *Listo* → publicado.
- **"Las tarifas no cambiaron"** → ya estaba todo publicado. Pasa si se ejecuta
  dos veces seguidas, o si el Excel se guardó sin cambios reales.
- **Avisos** → se publicó igual, pero conviene mirarlos (tarifas vencidas,
  rutas repetidas, tipos raros).
- **ERRORES** → **no se publicó nada**. Dice número de fila y problema.
  Se corrige el Excel y se vuelve a ejecutar.

Los celulares toman las tarifas nuevas al abrir la app, o al tocar el botón
de refrescar arriba a la derecha.

---

## Dónde vive la planilla

En el recurso compartido **`\\PC-02\Compartido\tarifas.xlsx`**, para que la
mantenga el operador desde su propia PC sin depender de esta.

La ruta está en **`planilla.txt`**, en la carpeta del proyecto: una sola línea
con la ruta completa. Si la planilla se muda, se cambia ahí y nada más. Si se
borra ese archivo, `PUBLICAR.bat` usa la copia local `datos\tarifas.xlsx`.

`PUBLICAR.bat` solo **lee** la planilla, así que puede estar abierta en Excel
mientras tanto — pero lee la última versión **guardada**.

Si PC-02 está apagada o fuera de la red, el publicador lo dice con ese texto y
no toca nada de lo que ya estaba publicado.

> `planilla.txt` no se sube al repositorio: no tiene sentido publicar los
> nombres de las máquinas de la oficina.

## La planilla

Hoja **TARIFAS**, una fila por tarifa:

| Columna | Obligatoria | Detalle |
|---|---|---|
| ORIGEN | sí | Ciudad o terminal |
| DESTINO | sí | Ciudad o terminal |
| TAMANO | sí | `20` o `40` |
| TIPO | sí | DRY, HC, REEFER, OPEN TOP, FLAT RACK, TANK |
| TARIFA | sí | Número puro: `1450`, no `U$S 1.450` |
| MONEDA | sí | `USD` o `ARS` |
| TRANSPORTISTA | no | Se muestra como etiqueta |
| VIGENCIA DESDE | no | Fecha |
| VIGENCIA HASTA | no | Vacío = sin vencimiento |
| OBSERVACIONES | no | Texto libre, aparece en la tarjeta |

No cambiar los nombres ni el orden de la fila 1. Mayúsculas y acentos no
importan para buscar: `San Rafael` y `SAN RAFAEL` son lo mismo.

Hoja **CONFIG**: la clave de acceso, el título y el nombre de la empresa.

---

## La clave de acceso

Está en la hoja **CONFIG**, fila `CLAVE_ACCESO`. Viene con `marblau2026`:
**cambiela antes de repartir la app.**

Las tarifas se publican **cifradas con esa clave** (AES-256). El archivo que
queda en internet es ilegible sin la clave, así que no hay problema en que el
repositorio sea público.

Si cambia la clave y vuelve a publicar, los usuarios ven un cartel pidiendo la
clave nueva. Es la forma de sacarle el acceso a alguien: cambiar la clave,
publicar y repartir la nueva al resto.

> El Excel guarda la clave en texto plano, por eso `.gitignore` excluye la
> carpeta `datos\`. **Nunca subir el Excel al repositorio.** Para respaldarlo,
> copiarlo a Google Drive.

---

## Probar sin publicar

Doble clic en **`PROBAR-EN-ESTA-PC.bat`**: abre la app en el navegador de esta
PC contra los datos ya generados. Dejar la ventana negra abierta mientras se
usa; cerrarla corta el servidor.

Sirve para revisar cómo quedó un cambio antes de que lo vean los demás —
siempre que se haya ejecutado `PUBLICAR.bat` primero.

---

## Instalar la app en el celular

Abrir la URL pública (ver `PUBLICAR-EN-INTERNET.md`) y:

- **Android / Chrome:** menú ⋮ → *Agregar a pantalla principal*.
- **iPhone / Safari:** botón compartir → *Agregar a inicio*.

Queda con ícono propio, pantalla completa y sin barra del navegador. Después de
la primera vez funciona **sin señal**, mostrando las últimas tarifas bajadas; el
encabezado avisa de cuándo son.

---

## Estructura

```
MarblauTarifas\
├─ PUBLICAR.bat              ← el operador usa esto
├─ PROBAR-EN-ESTA-PC.bat     ← previsualizar en esta PC
├─ planilla.txt              ← donde esta el Excel (hoy, en PC-02)
├─ datos\
│  ├─ tarifas.xlsx           ← copia local de respaldo, solo si falla la red
│  └─ .huella                ← para no republicar si nada cambio
├─ docs\                     ← la app publicada (GitHub Pages exige este nombre)
│  ├─ index.html, app.js, estilos.css, sw.js, manifest, iconos
│  └─ datos\tarifas.json     ← generado y cifrado por PUBLICAR.bat
├─ scripts\
│  ├─ publicar.py            ← valida, cifra y sube
│  ├─ crear_plantilla.py     ← regenera el Excel desde cero
│  └─ crear_iconos.py        ← regenera los iconos
└─ venv\                     ← Python local (openpyxl, cryptography, pillow)
```

---

## Si algo falla

| Síntoma | Qué pasa |
|---|---|
| `PUBLICAR.bat` dice ERRORES | Hay filas mal cargadas. Dice cuáles. No se publicó nada; el celular sigue con las tarifas anteriores. |
| La app pide la clave de nuevo | Cambió la `CLAVE_ACCESO` en el Excel. Repartir la nueva. |
| "Clave incorrecta" | La clave no coincide con la de la última publicación. |
| "Sin conexión" en el encabezado | El celular no tiene datos. Muestra lo último bajado y dice de cuándo es. |
| El celular no ve el cambio | Verificar que `PUBLICAR.bat` terminó con *Publicado en internet*. Después tocar el botón de refrescar en la app. |
| Tarifa marcada como vencida | La `VIGENCIA HASTA` de esa fila ya pasó. Actualizarla o vaciarla. |

---

## Detalles técnicos

- La app es una **PWA**: HTML, CSS y JavaScript sin dependencias externas, sin
  servidor propio y sin base de datos.
- `publicar.py` lee el Excel con `openpyxl`, valida fila por fila, arma un JSON
  y lo cifra con **AES-256-GCM**, con la llave derivada de la clave por
  **PBKDF2-SHA256** (210.000 iteraciones). El descifrado ocurre en el celular;
  la clave nunca viaja al servidor.
- El service worker cachea el armazón de la app, **no** las tarifas: estas se
  piden siempre a la red y la última copia descifrada queda en el celular. Así
  la app nunca muestra una tarifa vieja creyendo que es la actual.
- Requiere **https** (o `localhost`): el navegador no permite descifrar en
  conexiones inseguras. GitHub Pages ya sirve por https.

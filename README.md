# 📻 Grabador Automático de Radios en la Nube (Plan B Híbrido)

Sistema 100% automatizado en **GitHub Actions** para capturar radios peruanas sin anuncios extranjeros (vía túnel WireGuard `wireproxy` con failover automático), guardar respaldos en `.ts` por 3 días, auto-subir las grabaciones completas en **Privado (`[CRUDO]`)** a YouTube para detección nocturna de Content ID, y permitir recortes quirúrgicos instantáneos (**Stream Copy `-c copy`**) de inicio y tramos de copyright en minutos.

---

## 🏗️ Arquitectura del Sistema

### 1. Flujo Diario (Plan B Híbrido)
1. **Captura automática ([record_scheduled.yml](.github/workflows/record_scheduled.yml)):**
   * Arranca antes de cada ventana con **10 minutos de colchón inicial** y **+2 minutos al cierre** (`America/Lima`, GMT-5; día lógico inicia a las 05:00 AM).
   * Usa [capture_block.py](scripts/capture_block.py) + [vpn_manager.py](scripts/vpn_manager.py):
     * **VPN Just-in-Time:** Conecta `wireproxy` (~45s antes del primer show Mediastream) rotando automáticamente entre `PROTON_WG_CONF` → `PROTON_WG_CONF_2` → `PROTON_WG_CONF_3` tanto al inicio como **en plena grabación** si el nodo cae.
     * **Bloques nocturnos < 6h:** Divide la madrugada en `night_block_1` (hasta `22:50` Lima) y `night_block_2` (`22:50` → `04:02` Lima) para respetar el límite de 1 conexión simultánea de ProtonVPN Free y el límite de 6h de GitHub.
     * **Viva FM:** Graba directo sin VPN (`use_vpn: false`).
2. **Consolidación y Respaldo por 3 días ([finalize_audio.py](scripts/finalize_audio.py)):**
   * Une Parte 1 + Parte 2 en `audio.ts`.
   * Sube **GitHub Artifacts** (retención **3 días**, siempre antes de subir a YouTube):
     * `Previews_<Ventana>__YYYY-MM-DD`: MP3 ligeros de 45 min (64 kbps) de cada programa.
     * `Audio_<SLUG>__YYYY-MM-DD`: Audio maestro `.ts` íntegro de varias horas.
3. **Auto-Subida Nocturna (`[CRUDO]`) ([auto_upload.py](scripts/auto_upload.py) + [upload_youtube.py](scripts/upload_youtube.py)):**
   * Empaqueta cada audio a **1080×1080 (1 FPS, BT.709, CRF 18, Opus 320 kbps)** con [media_utils.py](scripts/media_utils.py).
   * Lo sube automáticamente en **Privado** al canal `b3TNvjWd` con título **`<PROGRAMA> - <FECHA> [CRUDO]`**, balanceando cuota diaria entre **`YT_TOKEN_1` .. `YT_TOKEN_10`** (con fallback automático si un proyecto llega a su límite).

---

## ✂️ Guía Paso a Paso: Cómo Recortar Inicio y Quitar Copyright (Plan B)

Cuando ya esté subido tu video **`[CRUDO]`** en YouTube Studio:

### Paso 1: Ubica los minutos en YouTube Studio
1. Abre **YouTube Studio → Contenido** y entra al video **`<PROGRAMA> - <FECHA> [CRUDO]`**.
2. Dale Play y adelanta los primeros ~10 minutos (colchón previo) para anotar en qué minuto/segundo exacto empieza la mejor canción o el mix (ej. **`11:24`** o **`25:18`**).
3. En la columna **Avisos / Restricciones**, revisa si alguna canción generó bloqueo por copyright y anota sus rangos exactos (ej. **`3:04:01-3:06:06, 7:21:00-7:23:41`**). *(Si no hay bloqueos, déjalo vacío).*

> 💡 Como el video `[CRUDO]` y el audio `.ts` guardado en GitHub arrancan exactamente en `00:00`, **los tiempos coinciden 1 a 1 sin tener que hacer restas manuales**.

### Paso 2: Llena el formulario en GitHub Actions
1. Ve a **Actions → `✂️ Plan B: Cortar y Subir a YouTube`** ([cut_and_upload.yml](.github/workflows/cut_and_upload.yml)).
2. Pulsa **`Run workflow`** y completa:
   * **1. Programa grabado:** elige el show exacto de la lista.
   * **2. Minuto exacto donde empieza el mix:** ej. `11:24` (o `01:05:12`).
   * **3. (Opcional) Minuto de corte final:** déjalo vacío para ir hasta el final, o pon un límite ej. `05:55:00`.
   * **4. (Opcional) Tramos con copyright a quitar:** déjalo vacío si está limpio, o escribe ej. `3:04:01-3:06:06, 7:21:00-7:23:41`.
   * **5. (Opcional) Fecha `YYYY-MM-DD`:** déjalo vacío para usar automáticamente la grabación más reciente.
   * **6. (Opcional) Título personalizado:** déjalo vacío para generar `<PROGRAMA> - DD MES AAAA` (ya sin `[CRUDO]`).
   * **7. Visibilidad:** `private` (por defecto), `unlisted` o `public`.
   * **8. Solo generar MP4 descargable:** déjalo desmarcado para subir directo a YouTube (o márcalo si prefieres bajar el `.mp4` desde Artifacts).
3. Pulsa el botón verde **`Run workflow`**.

### Paso 3: Verificación final en YouTube
* En **~2 a 4 minutos**, [cut_and_upload.py](scripts/cut_and_upload.py) descarga el `.ts` desde Artifacts, recorta y une tramos limpios sin recodificar el audio (`-c copy`), empaqueta el MP4 1080p y sube la versión definitiva limpia al canal.
* Revisa el nuevo video en YouTube Studio y borra el borrador anterior **`[CRUDO]`**.

---

## 📅 Grilla Programada (`America/Lima` GMT-5)

Definida en [config/schedule.json](config/schedule.json) (sincronizada con `main.js` de la web):

| Programa | Emisora | Días | Horario Oficial |
| :--- | :--- | :--- | :--- |
| **PANAMERICANA PANAMIX** | Panamericana | Lun–Vie | `12:00 PM – 01:00 PM` |
| **LA ZONA CLASICOS DEL REGGAETON** | La Zona | Vie | `03:00 PM – 04:00 PM` |
| **VIVA FM FIESTA PRIVADA** | Viva FM | Vie–Sáb | `07:00 PM – 12:00 AM` |
| **ONDA CERO LA HORA REMIX** | Onda Cero | Lun–Jue | `09:00 PM – 10:00 PM` |
| **LA ZONA ZONA WEEKEND CLASICOS** | La Zona | Sáb–Dom | `06:00 PM – 12:00 AM` |
| **STUDIO MODO LATIN** | Studio 92 | Sáb | `07:00 PM – 08:00 PM` |
| **PLANETA WEEKEND** | Planeta | Vie | `08:00 PM – 02:00 AM` |
| **PLANETA WEEKEND** | Planeta | Sáb | `07:55 PM – 02:00 AM` |
| **MODA EL JUERGON DE MODA** | Moda | Vie–Sáb | `08:00 PM – 04:00 AM` |
| **MODA EL JUERGON DE MODA** | Moda | Dom | `09:00 PM – 04:00 AM` |
| **STUDIO SESSIONS** | Studio 92 | Vie–Sáb | `08:00 PM – 12:00 AM` |
| **OXIGENO BAR OXIGENO** | Oxígeno | Vie | `09:00 PM – 12:00 AM` |
| **OXIGENO BAR OXIGENO** | Oxígeno | Sáb | `08:00 PM – 12:00 AM` |
| **LA ZONA ZONA WEEKEND** | La Zona | Vie | `09:00 PM – 02:00 AM` |
| **ONDA CERO LA TOCADA** | Onda Cero | Vie–Sáb | `09:00 PM – 02:00 AM` |
| **PANAMERICANA PANAMIX** | Panamericana | Sáb | `10:00 PM – 12:00 AM` |

---

## 🔐 GitHub Secrets Configurados
* **VPN ProtonVPN (WireGuard Europeos):**
  * `PROTON_WG_CONF` (`RO-FREE#28` principal)
  * `PROTON_WG_CONF_2` (`RO-FREE#21` respaldo 1)
  * `PROTON_WG_CONF_3` (`NL-FREE#151` respaldo 2)
* **YouTube Data API v3 (Canal `b3TNvjWd`, ~6 subidas/día por proyecto):**
  * `YT_TOKEN_1` (Proyecto 1)
  * `YT_TOKEN_2` (Proyecto 2)
  * `YT_TOKEN_3` (Proyecto 3 — total ~18 subidas/día)

> ⚠️ **Nota para agentes/mantenimiento:** `*.conf` y `client_secret*.json` están bloqueados en [.gitignore](.gitignore) para nunca exponerse en el repositorio público.

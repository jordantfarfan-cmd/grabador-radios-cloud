# 📻 Grabador Automático de Radios en la Nube (Cloud Recorder)

Sistema de grabación de radios peruanas en streaming 100% automatizado, ejecutado en la nube con **GitHub Actions**, sin emular navegadores ni consumir recursos de tu PC local.

---

## 🚀 Características Principales

* **Transmisión Directa:** Se conecta a los endpoints Icecast directos de **Mediastream** y **TuPanel** sin depender de interfaces web ni requerir clics.
* **Calidad de Audio de Estudio:** Codificado en **Opus a 320 kbps** (`-c:a libopus -b:a 320k`).
* **Calidad de Video Cristalina:** Formato 1:1 (1080x1080) a 1 FPS con `-crf 18` y ajuste de escala par automático para máxima nitidez de portada.
* **Tolerancia a Cortes:** Captura continua en formato de transporte `.ts` con bucle de reconexión automática; los archivos nunca se corrompen ante microcortes.
* **Shows Extendidos (hasta 10 horas):** Divide automáticamente shows largos en 2 bloques secuenciales y los une en un único archivo MP4 final en tu Google Drive.
* **Almacenamiento Eficiente:** Artefactos temporales de GitHub con auto-eliminación a las 24 horas (`retention-days: 1`).
* **Subida Automática a Google Drive:** Conexión permanente con `rclone` (OAuth en Producción).

---

## 🛠️ Configuración Inicial en 3 Pasos

### Paso 1: Configurar Google Drive en tu PC con rclone (Una sola vez)
1. Descarga e instala `rclone` en tu PC (desde https://rclone.org/downloads/).
2. Abre la consola y ejecuta:
   ```bash
   rclone config
   ```
3. Sigue los pasos interactivos:
   * Escribe `n` para un nuevo remoto.
   * Nombre: `gdrive`
   * Tipo de almacenamiento: Busca `drive` (Google Drive).
   * Deja `client_id` y `client_secret` en blanco si deseas, o usa tus propias credenciales de Google Cloud Console (recomendado con la app en estado **"In Production"**).
   * Scope: Elige `1` (Full access).
   * Al final te abrirá el navegador para iniciar sesión con tu cuenta de Google.
4. Abre el archivo de configuración que generó rclone (usualmente en `%APPDATA%\rclone\rclone.conf` en Windows o `~/.config/rclone/rclone.conf` en Linux/Mac) y **copia todo su contenido de texto**.

### Paso 2: Agregar el Secret en GitHub
1. En tu repositorio de GitHub, ve a **Settings** > **Secrets and variables** > **Actions**.
2. Haz clic en **New repository secret**.
3. **Nombre del secreto:** `RCLONE_CONFIG`
4. **Valor del secreto:** Pega todo el contenido de tu archivo `rclone.conf`.
5. Guarda los cambios.

### Paso 3: Probar el sistema con la prueba de 30 segundos
1. En tu repositorio en GitHub, ve a la pestaña **Actions**.
2. En la lista izquierda, haz clic en **"Prueba 30 Segundos - 8 Radios"**.
3. Haz clic en **Run workflow** > **Run workflow**.
4. GitHub encenderá 8 máquinas en paralelo en EE. UU., grabará 30 segundos de cada emisora, generará los MP4s con portada y los subirá a tu Google Drive (en `Grabaciones_Radio/Pruebas`) o los dejará disponibles para descargar en la misma pestaña de Actions.

---

## 📅 Grilla de Programas y Emisoras

* **Moda:** `https://mdstrm.com/audio/6839e1c82cc4c480fcd318dd/icecast.audio`
* **Planeta:** `https://mdstrm.com/audio/6839e274f40e6b9832e37633/icecast.audio`
* **Onda Cero:** `https://mdstrm.com/audio/6598b65ab398c90871aff8cc/icecast.audio`
* **Panamericana:** `https://mdstrm.com/audio/6598b62dded1380470f4e539/icecast.audio`
* **Studio 92:** `https://mdstrm.com/audio/5fada553978fe1080e3ac5ea/icecast.audio`
* **La Zona:** `https://mdstrm.com/audio/5fada54116646e098d97e6a5/icecast.audio`
* **Oxígeno:** `https://mdstrm.com/audio/5fab0687bcd6c2389ee9480c/icecast.audio`
* **Viva FM:** `https://tupanel.info:8780/stream`

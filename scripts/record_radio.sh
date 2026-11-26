#!/usr/bin/env bash
# ==============================================================================
# SCRIPT MAESTRO DE GRABACIÓN DE RADIOS - CLOUD RECORDER (BLINDADO)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ARG1="$1"
ARG2="$2"
ARG3="$3"
ARG4="$4"
ARG5="$5"
ARG6="$6"

SHOW_NAME="${ARG1:-"RADIO_TEST"}"
STREAM_URL="${ARG2:-""}"

# Detección inteligente de argumentos (por si un entorno omite un string vacío)
if [[ "$ARG3" =~ ^[0-9]+$ ]]; then
    # ARG3 es un número: fue invocado como: script name url duration folder [slot_index]
    COVER_URL=""
    DURATION="$ARG3"
    GDRIVE_FOLDER="${ARG4:-"Grabaciones_Radio"}"
    SLOT_INDEX="${ARG5:-${YT_SLOT_INDEX:-1}}"
else
    COVER_URL="${ARG3:-""}"
    DURATION="${ARG4:-30}"
    GDRIVE_FOLDER="${ARG5:-"Grabaciones_Radio"}"
    SLOT_INDEX="${ARG6:-${YT_SLOT_INDEX:-1}}"
fi

# Sanitizar duración (solo números enteros)
DURATION=$(echo "$DURATION" | tr -dc '0-9')
DURATION="${DURATION:-30}"

if [ -z "$STREAM_URL" ]; then
    echo "ERROR: La URL del streaming no puede estar vacía."
    exit 1
fi

echo "================================================================="
echo " INICIANDO GRABACIÓN: $SHOW_NAME"
echo " Stream URL: $STREAM_URL"
echo " Duración: ${DURATION}s ($(( DURATION / 60 )) min)"
echo " Destino Drive: $GDRIVE_FOLDER"
echo "================================================================="

WORKDIR="temp_${SHOW_NAME// /_}"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# 1. Descargar carátula oficial si es una URL válida
echo "--> Verificando carátula oficial..."
if [[ "$COVER_URL" == http* ]]; then
    echo "--> Descargando imagen desde $COVER_URL..."
    curl -sSL --retry 3 -o "cover.png" "$COVER_URL" || true
fi

# Fallback si no existe o pesa 0 bytes: generar un fondo negro 1080x1080
if [ ! -s "cover.png" ]; then
    echo "--> Generando carátula neutra 1080x1080..."
    ffmpeg -y -f lavfi -i color=c=black:s=1080x1080:d=1 -frames:v 1 -update 1 cover.png
fi

# 2. Bucle de captura tolerante a caídas (graba en formato MPEG-TS)
TARGET_END=$(( $(date +%s) + DURATION ))
PART=1

echo "--> Iniciando captura de stream a formato .ts..."
while [ $(date +%s) -lt $TARGET_END ]; do
    NOW=$(date +%s)
    REMAINING=$(( TARGET_END - NOW ))
    
    # Si quedan 2 segundos o menos, finalizamos el bucle
    if [ $REMAINING -le 2 ]; then
        break
    fi
    
    PART_FILE=$(printf "parte_%03d.ts" $PART)
    echo "-> Capturando $PART_FILE (restante: ${REMAINING}s)..."
    
    # Flags de reconexión y timeout seguro (usando proxy VPN si STREAM_HTTP_PROXY está definido)
    PROXY_OPTS=()
    if [ -n "${STREAM_HTTP_PROXY:-}" ]; then
        PROXY_OPTS=(-http_proxy "$STREAM_HTTP_PROXY")
    fi

    http_proxy="${STREAM_HTTP_PROXY:-}" https_proxy="${STREAM_HTTP_PROXY:-}" ffmpeg -y \
        -reconnect 1 \
        -reconnect_streamed 1 \
        -reconnect_delay_max 5 \
        -rw_timeout 15000000 \
        "${PROXY_OPTS[@]}" \
        -i "$STREAM_URL" \
        -t "$REMAINING" \
        -c:a copy \
        -f mpegts \
        "$PART_FILE" || true
    
    PART=$(( PART + 1 ))
    sleep 1
done

# 3. Concatenar partes si hubo microcortes
PARTS_COUNT=$(ls parte_*.ts 2>/dev/null | wc -l)
if [ "$PARTS_COUNT" -eq 0 ]; then
    echo "ERROR CRÍTICO: No se capturó ningún paquete de audio del streaming."
    exit 1
fi

echo "--> Verificando fragmentos de audio capturados ($PARTS_COUNT partes)..."
if [ "$PARTS_COUNT" -eq 1 ]; then
    cp parte_001.ts audio_completo.ts
else
    # Generar lista ordenada numéricamente
    > lista.txt
    for f in $(ls -v parte_*.ts); do
        echo "file '$f'" >> lista.txt
    done
    ffmpeg -y -f concat -safe 0 -i lista.txt -c copy audio_completo.ts
fi

# 4. Empaquetar a MP4 Final y Subir (con cola flock para proteger RAM en Oracle 1GB)
FECHA_LIMA=$(TZ="America/Lima" date +"%Y-%m-%d_%H-%M")
OUTPUT_MP4="${SHOW_NAME} - ${FECHA_LIMA}.mp4"

pack_and_upload() {
    AUDIO_DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 audio_completo.ts || true)
    DUR_OPT=()
    if [ -n "$AUDIO_DUR" ] && [ "$AUDIO_DUR" != "N/A" ]; then
        DUR_OPT=(-t "$AUDIO_DUR")
    fi

    echo "--> Generando MP4 final con carátula 1080x1080 y audio Opus 320 kbps (Color BT.709, Duración: ${AUDIO_DUR:-auto}s)..."
    ffmpeg -y \
        -loop 1 -framerate 1 "${DUR_OPT[@]}" -i cover.png \
        -i audio_completo.ts \
        -vf "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2,scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p" \
        -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
        -c:v libx264 -tune stillimage -preset ultrafast -crf 18 \
        -c:a libopus -b:a 320k \
        "${DUR_OPT[@]}" \
        -shortest \
        -movflags +faststart \
        "$OUTPUT_MP4"

    echo "--> MP4 generado con éxito: $OUTPUT_MP4 (Tamaño: $(du -h "$OUTPUT_MP4" | cut -f1))"

    # 5. Subida directa a YouTube (si YT_TOKEN_1 o YT_TOKEN_2 están configurados)
    if [ -n "${YT_TOKEN_1:-}" ] || [ -n "${YT_TOKEN_2:-}" ]; then
        TITULO_FECHA=$(TZ="America/Lima" date +"%d %b %Y" | tr '[:lower:]' '[:upper:]')
        YT_TITLE="${SHOW_NAME} - ${TITULO_FECHA}"
        echo "--> Subiendo directo a YouTube (Privado) [Slot #${SLOT_INDEX}]: $YT_TITLE"
        python3 "$SCRIPT_DIR/upload_youtube.py" \
            --file "$OUTPUT_MP4" \
            --title "$YT_TITLE" \
            --description "Grabación automática de ${SHOW_NAME} (${TITULO_FECHA})." \
            --privacy "private" \
            --slot-index "$SLOT_INDEX"
    fi

    # 6. Respaldo opcional en Google Drive solo si rclone está configurado
    if command -v rclone &> /dev/null && [ -f "$HOME/.config/rclone/rclone.conf" ]; then
        echo "--> Subiendo a Google Drive ($GDRIVE_FOLDER)..."
        rclone move "$OUTPUT_MP4" "gdrive:$GDRIVE_FOLDER" --progress
        echo "--> ¡Subida a Google Drive completada!"
    fi
}

if [ "${RECORD_MODE:-full}" = "capture_only" ]; then
    echo "--> Modo capture_only: conservando audio_completo.ts para unión posterior."
    rm -f parte_*.ts lista.txt
    echo "================================================================="
    echo " CAPTURA PARCIAL FINALIZADA: $SHOW_NAME"
    echo "================================================================="
    exit 0
fi

if command -v flock &> /dev/null; then
    echo "--> Esperando turno en cola (flock) para empaquetar sin saturar RAM..."
    (
        flock -x 200
        pack_and_upload
    ) 200>/tmp/radio_muxer.lock
else
    pack_and_upload
fi

# Limpieza de archivos temporales
rm -f parte_*.ts audio_completo.ts cover.png lista.txt

echo "================================================================="
echo " PROCESO FINALIZADO CON ÉXITO: $SHOW_NAME"
echo "================================================================="

#!/usr/bin/env bash
# ==============================================================================
# SCRIPT DE UNIÓN DE PARTES (PARA SHOWS EXTENDIDOS > 5 HORAS)
# ==============================================================================
# Parámetros:
# $1: Nombre del Programa (ej. "LA ZONA ZONA WEEKEND CLASICOS")
# $2: URL de la carátula en GitHub
# $3: Carpeta de destino en Google Drive
# ==============================================================================

set -e

SHOW_NAME="${1:-"RADIO_SHOW"}"
COVER_URL="${2:-""}"
GDRIVE_FOLDER="${3:-"Grabaciones_Radio"}"

echo "================================================================="
echo " UNIENDO BLOQUES DE SHOW EXTENDIDO: $SHOW_NAME"
echo "================================================================="

# 1. Descargar carátula
if [ -n "$COVER_URL" ]; then
    curl -sSL --retry 3 -o "cover.png" "$COVER_URL" || true
fi
if [ ! -s "cover.png" ]; then
    ffmpeg -y -f lavfi -i color=c=black:s=1080x1080:d=1 -frames:v 1 cover.png
fi

# 2. Verificar existencia de las partes .ts
PARTS_COUNT=$(ls parte_*.ts 2>/dev/null | wc -l)
if [ "$PARTS_COUNT" -eq 0 ]; then
    echo "ERROR: No se encontraron partes .ts para unir."
    exit 1
fi

echo "--> Partes encontradas: $PARTS_COUNT"
> lista.txt
for f in $(ls -v parte_*.ts); do
    echo "file '$f'" >> lista.txt
    echo "  -> Incluyendo $f ($(du -h "$f" | cut -f1))"
done

echo "--> Concatenando audio continuo sin recodificar..."
ffmpeg -y -f concat -safe 0 -i lista.txt -c copy audio_unido.ts

# 3. Empaquetar a MP4 Final
FECHA_LIMA=$(TZ="America/Lima" date +"%Y-%m-%d_%H-%M")
OUTPUT_MP4="${SHOW_NAME} - ${FECHA_LIMA}.mp4"

AUDIO_DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 audio_unido.ts || true)
DUR_OPT=()
if [ -n "$AUDIO_DUR" ] && [ "$AUDIO_DUR" != "N/A" ]; then
    DUR_OPT=(-t "$AUDIO_DUR")
fi

echo "--> Generando MP4 unificado final (Color BT.709, Duración: ${AUDIO_DUR:-auto}s)..."
ffmpeg -y \
    -loop 1 -framerate 1 "${DUR_OPT[@]}" -i cover.png \
    -i audio_unido.ts \
    -vf "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2,scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p" \
    -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
    -c:v libx264 -tune stillimage -preset ultrafast -crf 18 \
    -c:a libopus -b:a 320k \
    "${DUR_OPT[@]}" \
    -shortest \
    -movflags +faststart \
    "$OUTPUT_MP4"

echo "--> MP4 generado: $OUTPUT_MP4 (Tamaño: $(du -h "$OUTPUT_MP4" | cut -f1))"

# 4. Subida a Google Drive
if command -v rclone &> /dev/null && [ -f "$HOME/.config/rclone/rclone.conf" ]; then
    echo "--> Subiendo archivo unificado a Google Drive..."
    rclone move "$OUTPUT_MP4" "gdrive:$GDRIVE_FOLDER" --progress
    echo "--> ¡Subida completada con éxito!"
fi

# Limpieza
rm -f parte_*.ts audio_unido.ts cover.png lista.txt
echo "================================================================="

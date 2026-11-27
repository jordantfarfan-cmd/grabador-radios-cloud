#!/usr/bin/env python3
"""
Utilidades compartidas de audio/video FFmpeg para el grabador en la nube.
"""

import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo


def safe_slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")


def parse_timestamp(ts: str) -> float:
    """Convierte 'SS', 'MM:SS' o 'HH:MM:SS' (con decimales opcionales) a segundos."""
    clean = ts.strip()
    if not clean:
        raise ValueError("Timestamp vacío")
    parts = clean.split(":")
    if len(parts) > 3:
        raise ValueError(f"Formato de tiempo inválido: '{ts}'")
    vals = [float(p) for p in parts]
    if any(v < 0 for v in vals):
        raise ValueError(f"El tiempo no puede ser negativo: '{ts}'")
    if len(vals) == 1:
        return vals[0]
    if len(vals) == 2:
        return vals[0] * 60 + vals[1]
    return vals[0] * 3600 + vals[1] * 60 + vals[2]


def format_timestamp(seconds: float) -> str:
    """Formatea segundos como HH:MM:SS.mmm para FFmpeg."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def format_date_es(date_str: str) -> str:
    months = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day:02d} {months[dt.month - 1]} {dt.year}"
    except Exception:
        now = datetime.now(ZoneInfo("America/Lima"))
        return f"{now.day:02d} {months[now.month - 1]} {now.year}"


SHOW_TEMPLATES = {
    "PANAMERICANA PANAMIX": (
        '"-" / [PANAMERICANA] 🎼 PANAMIX 🎼 {date}',
        "👉 Sigue a DJ Bans: https://www.instagram.com/djbansdamemas/",
    ),
    "LA ZONA CLASICOS DEL REGGAETON": (
        '"-" / [LA ZONA] 🔥 CLÁSICOS DEL REGGAETON 🔥 {date}',
        "👉 Sigue a DJ Urbano: https://www.instagram.com/djurbano.peru/",
    ),
    "VIVA FM FIESTA PRIVADA": (
        '"-" / [VIVA FM] 🎫 FIESTA PRIVADA 🎫 {date}',
        "👉 Sigue a DJ Chris: https://www.instagram.com/djchrisperu/",
    ),
    "LA ZONA ZONA WEEKEND CLASICOS DEL REGGAETON": (
        '"-" / [LA ZONA] 🏖️🔥 ZONA WEEKEND: CLÁSICOS DEL REGGAETON 🔥🏖️ {date}',
        "👉 Sigue a DJ Urbano: https://www.instagram.com/djurbano.peru/",
    ),
    "STUDIO MODO LATIN": (
        '"-" / [STUDIO 92] 🧃 MODO LATIN 🧃 {date}',
        "👉 Sigue a DJ RED: https://www.instagram.com/djredperu/",
    ),
    "PLANETA PLANETA WEEKEND": (
        '"-" / [PLANETA] 🪐 PLANETA WEEKEND 🪐 {date}',
        "👉 Sigue a DJ GIAN: https://www.instagram.com/djgianperu/",
    ),
    "MODA EL JUERGON DE MODA": (
        '"-" / [MODA] 💥 EL JUERGÓN DE MODA 💥 {date}',
        "👉 Sigue a DJ GIAN: https://www.instagram.com/djgianperu/",
    ),
    "STUDIO SESSIONS": (
        '"-" / [STUDIO 92] 🎧 SESSIONS 🎧 {date}',
        "👉 Sigue a DJ RED: https://www.instagram.com/djredperu/",
    ),
    "OXIGENO BAR OXIGENO": (
        '"-" / [OXÍGENO] 🍸 BAR OXÍGENO 🍸 {date}',
        "👉 Sigue a DJ Fresh: https://www.facebook.com/Djfresheventos/",
    ),
    "LA ZONA ZONA WEEKEND": (
        '"-" / [LA ZONA] 🏖️ ZONA WEEKEND 🏖️ {date}',
        "👉 Sigue a DJ Urbano: https://www.instagram.com/djurbano.peru/",
    ),
    "ONDA CERO LA TOCADA": (
        '"-" / [ONDA CERO] 🏓 LA TOCADA 🏓 {date}',
        "👉 Sigue a DJ Mariane: https://www.instagram.com/djmarianeperu/\n👉 Sigue a DJ Bans: https://www.instagram.com/djbansdamemas/",
    ),
}


def get_default_youtube_metadata(show_name: str, date_label: str) -> tuple[str, str]:
    tpl = SHOW_TEMPLATES.get(show_name)
    if tpl:
        return tpl[0].format(date=date_label), tpl[1]
    return f"{show_name} - {date_label}", f"Grabación de {show_name} ({date_label})."


SHOW_PLAYLISTS = {
    "PANAMERICANA PANAMIX": "[PANAMERICANA] 🎼 PANAMIX 🎼",
    "LA ZONA CLASICOS DEL REGGAETON": "[LA ZONA] 🔥 CLÁSICOS DEL REGGAETON 🔥",
    "LA ZONA ZONA WEEKEND CLASICOS DEL REGGAETON": "[LA ZONA] 🔥 CLÁSICOS DEL REGGAETON 🔥",
    "MODA EL JUERGON DE MODA": "[MODA] 💥 EL JUERGÓN DE MODA 💥",
    "PLANETA PLANETA WEEKEND": "[PLANETA] 🪐 PLANETA WEEKEND 🪐",
    "OXIGENO BAR OXIGENO": "[OXÍGENO] 🍸 BAR OXÍGENO 🍸",
    "STUDIO SESSIONS": "[STUDIO 92] 🎧 SESSIONS 🎧",
    "ONDA CERO LA TOCADA": "[ONDA CERO] 🏓 LA TOCADA 🏓",
    "VIVA FM FIESTA PRIVADA": "[VIVA FM] 🎫 FIESTA PRIVADA 🎫",
    "STUDIO MODO LATIN": "[STUDIO 92] 🧃 MODO LATIN 🧃",
    "LA ZONA ZONA WEEKEND": "[LA ZONA] 🏖️ ZONA WEEKEND 🏖️",
}


def get_default_playlist(show_name: str) -> str:
    return SHOW_PLAYLISTS.get(show_name, "")


def probe_duration(file_path: str) -> float:
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True, text=True, check=True,
    )
    raw = probe.stdout.strip()
    if not raw or raw == "N/A":
        raise RuntimeError(f"No se pudo medir la duración de {file_path}")
    return float(raw)


def download_cover(cover_file: str, covers_base_url: str, dest_path: str) -> str:
    cover_url = covers_base_url + cover_file
    subprocess.run(["curl", "-sSL", "--retry", "3", "-o", dest_path, cover_url], check=False)
    if not os.path.isfile(dest_path) or os.path.getsize(dest_path) == 0:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1080:d=1", "-frames:v", "1", "-update", "1", dest_path],
            check=True,
        )
    return dest_path


def mux_mp4(cover_path: str, audio_path: str, output_mp4: str, dur_sec: float | None = None):
    """Empaqueta carátula 1080x1080 (1 FPS, BT.709, CRF 18) + audio Opus 320 kbps."""
    dur_args = ["-t", f"{dur_sec:.3f}"] if dur_sec and dur_sec > 0 else []
    mux_cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-loop", "1", "-framerate", "1", *dur_args, "-i", cover_path,
        "-i", audio_path,
        "-vf", "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2,scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "libopus", "-b:a", "320k",
        *dur_args,
        "-shortest",
        "-movflags", "+faststart",
        output_mp4,
    ]
    subprocess.run(mux_cmd, check=True)

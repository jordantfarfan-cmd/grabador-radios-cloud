#!/usr/bin/env python3
"""
Plan B: Cortador Instantáneo (Stream Copy) + Empaquetador 1080p BT.709 + Subidor a YouTube
- Descarga automáticamente el audio .ts más reciente del programa elegido desde GitHub Artifacts.
- Corta exactamente desde el minuto de inicio (--start) hasta el final (o --end) sin recodificar audio.
- Empaqueta con la carátula 1080x1080 1 FPS BT.709 CRF 18 + Opus 320 kbps.
- Sube directo al canal b3TNvjWd en Privado con balanceo automático YT_TOKEN_1 / YT_TOKEN_2.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


def safe_slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")


def find_latest_artifact(repo: str, slug: str, target_date: str = ""):
    prefix = f"Audio_{slug}__"
    if target_date:
        prefix = f"Audio_{slug}__{target_date}"

    cmd = [
        "gh", "api",
        f"repos/{repo}/actions/artifacts?per_page=100",
        "--jq", ".artifacts"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    artifacts = json.loads(res.stdout)

    matches = [
        a for a in artifacts
        if not a.get("expired") and a.get("name", "").startswith(prefix)
    ]
    if not matches:
        return None
    matches.sort(key=lambda x: x["created_at"], reverse=True)
    return matches[0]


def format_date_es(date_str: str) -> str:
    months = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day:02d} {months[dt.month - 1]} {dt.year}"
    except Exception:
        now = datetime.now(ZoneInfo("America/Lima"))
        return f"{now.day:02d} {months[now.month - 1]} {now.year}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", required=True, help="Nombre exacto del programa")
    parser.add_argument("--start", default="00:00", help="Minuto de inicio (ej. 07:35 o 00:35:10)")
    parser.add_argument("--end", default="", help="Minuto de fin opcional (ej. 03:55:00)")
    parser.add_argument("--date", default="", help="Fecha opcional YYYY-MM-DD (por defecto la más reciente)")
    parser.add_argument("--title", default="", help="Título personalizado opcional para YouTube")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("ERROR: GITHUB_REPOSITORY no está definido.", file=sys.stderr)
        sys.exit(1)

    slug = safe_slug(args.show)
    print(f"--> Buscando grabación más reciente para: {args.show} (slug: {slug})...")
    artifact = find_latest_artifact(repo, slug, args.date.strip())
    if not artifact:
        print(f"ERROR: No se encontró ningún audio guardado para '{args.show}' (prefijo Audio_{slug}__).", file=sys.stderr)
        sys.exit(1)

    run_id = artifact["workflow_run"]["id"]
    art_name = artifact["name"]
    art_date = art_name.split("__")[-1] if "__" in art_name else ""
    size_mb = artifact["size_in_bytes"] / (1024 * 1024)
    print(f"--> Encontrado: {art_name} ({size_mb:.1f} MB, Run #{run_id})")

    work_dir = "work_cut"
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir, exist_ok=True)

    print("--> Descargando audio desde GitHub Artifacts...")
    subprocess.run(
        ["gh", "run", "download", str(run_id), "-n", art_name, "-D", work_dir],
        check=True,
    )

    # Localizar audio.ts y meta.json
    audio_ts = None
    meta_json = None
    for root, _, files in os.walk(work_dir):
        if "audio.ts" in files:
            audio_ts = os.path.join(root, "audio.ts")
        if "meta.json" in files:
            meta_json = os.path.join(root, "meta.json")

    if not audio_ts or not os.path.isfile(audio_ts):
        print("ERROR: No se encontró audio.ts dentro del artefacto.", file=sys.stderr)
        sys.exit(1)

    meta = {}
    if meta_json and os.path.isfile(meta_json):
        with open(meta_json, "r", encoding="utf-8") as f:
            meta = json.load(f)

    cover_file = meta.get("cover", f"{args.show.replace(' ', '%20')}.png")
    with open("config/schedule.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cover_url = cfg["covers_base_url"] + cover_file

    # Descargar carátula
    cover_path = os.path.join(work_dir, "cover.png")
    subprocess.run(["curl", "-sSL", "--retry", "3", "-o", cover_path, cover_url], check=False)
    if not os.path.isfile(cover_path) or os.path.getsize(cover_path) == 0:
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1080:d=1", "-frames:v", "1", "-update", "1", cover_path], check=True)

    # Recorte instantáneo por Stream Copy
    cut_ts = os.path.join(work_dir, "audio_cortado.ts")
    start_str = args.start.strip() or "0"
    end_str = args.end.strip()

    if start_str in ("0", "00:00", "0:00", "00:00:00") and not end_str:
        print("--> Sin recorte solicitado (inicio 00:00). Usando audio íntegro...")
        shutil.copy2(audio_ts, cut_ts)
    else:
        print(f"--> Recortando audio al instante (Stream Copy): inicio={start_str}, fin={end_str or 'final'}...")
        cut_cmd = ["ffmpeg", "-y", "-loglevel", "warning", "-ss", start_str]
        if end_str:
            cut_cmd += ["-to", end_str]
        cut_cmd += ["-i", audio_ts, "-c", "copy", cut_ts]
        subprocess.run(cut_cmd, check=True)

    # Medir duración exacta del audio recortado
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", cut_ts],
        capture_output=True, text=True, check=True,
    )
    dur_sec = probe.stdout.strip()
    print(f"--> Duración final exacta tras recorte: {dur_sec}s")

    # Empaquetar a MP4 Final 1080x1080 1 FPS BT.709 CRF 18 + Opus 320 kbps
    final_mp4 = os.path.join(work_dir, "final_video.mp4")
    dur_args = ["-t", dur_sec] if dur_sec and dur_sec != "N/A" else []

    print("--> Empaquetando MP4 1080x1080 (BT.709, CRF 18, Opus 320 kbps)...")
    mux_cmd = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-loop", "1", "-framerate", "1", *dur_args, "-i", cover_path,
        "-i", cut_ts,
        "-vf", "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2,scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "libopus", "-b:a", "320k",
        *dur_args,
        "-shortest",
        "-movflags", "+faststart",
        final_mp4,
    ]
    subprocess.run(mux_cmd, check=True)
    mp4_mb = os.path.getsize(final_mp4) / (1024 * 1024)
    print(f"✅ MP4 listo para subir ({mp4_mb:.1f} MB)")

    # Título para YouTube
    date_label = format_date_es(meta.get("date", art_date))
    yt_title = args.title.strip() if args.title.strip() else f"{args.show} - {date_label}"

    print(f"--> Subiendo directo a YouTube ({args.privacy}): {yt_title}")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(
        [
            sys.executable, os.path.join(script_dir, "upload_youtube.py"),
            "--file", final_mp4,
            "--title", yt_title,
            "--description", f"Grabación de {args.show} ({date_label}).",
            "--privacy", args.privacy,
            "--slot-index", "1",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()

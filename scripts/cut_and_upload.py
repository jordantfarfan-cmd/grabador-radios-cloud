#!/usr/bin/env python3
"""
Plan B: Cortador Instantáneo (Stream Copy + Múltiples Cortes Copyright) + Empaquetador 1080p BT.709
- Descarga automáticamente el audio .ts más reciente del programa elegido desde GitHub Artifacts.
- Recorta el inicio (--start), opcionalmente el final (--end), y elimina múltiples tramos
  impugnados por copyright (--exclude "45:12-48:30, 01:52:10-01:55:40") mediante Stream Copy (-c copy).
- Empaqueta con carátula 1080x1080 1 FPS BT.709 CRF 18 + Opus 320 kbps.
- Sube directo al canal en Privado (o guarda el MP4 listo para descargar si se pasa --download-only).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from media_utils import (
    download_cover,
    format_date_es,
    format_timestamp,
    get_default_youtube_metadata,
    mux_mp4,
    parse_timestamp,
    probe_duration,
    safe_slug,
)


def find_latest_artifact(repo: str, slug: str, target_date: str = ""):
    prefix = f"Audio_{slug}__"
    if target_date:
        prefix = f"Audio_{slug}__{target_date}"

    cmd = [
        "gh", "api",
        f"repos/{repo}/actions/artifacts?per_page=100",
        "--jq", ".artifacts",
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


def compute_keep_segments(win_start: float, win_end: float, exclude_raw: str) -> list[tuple[float, float]]:
    """Calcula los tramos limpios dentro de [win_start, win_end] tras restar las zonas excluidas."""
    if not exclude_raw.strip():
        return [(win_start, win_end)]

    exclusions = []
    tokens = [t.strip() for t in exclude_raw.replace(";", ",").split(",") if t.strip()]
    for tok in tokens:
        if "-" not in tok:
            raise ValueError(f"Tramo de exclusión inválido '{tok}'. Usa formato INICIO-FIN, ej: 45:12-48:30")
        left, right = tok.split("-", 1)
        ex_s = parse_timestamp(left)
        ex_e = parse_timestamp(right)
        if ex_e <= ex_s:
            raise ValueError(f"El fin debe ser mayor al inicio en el tramo '{tok}'")
        cs = max(win_start, ex_s)
        ce = min(win_end, ex_e)
        if ce > cs:
            exclusions.append((cs, ce))

    if not exclusions:
        return [(win_start, win_end)]

    exclusions.sort()
    merged = [exclusions[0]]
    for s, e in exclusions[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    kept = []
    cursor = win_start
    for ex_s, ex_e in merged:
        if ex_s - cursor >= 0.5:
            kept.append((cursor, ex_s))
        cursor = max(cursor, ex_e)
    if win_end - cursor >= 0.5:
        kept.append((cursor, win_end))

    if not kept:
        raise ValueError("Los tramos excluidos eliminan todo el programa.")
    return kept


def build_cut_audio(audio_ts: str, work_dir: str, segments: list[tuple[float, float]], total_dur: float) -> str:
    cut_ts = os.path.join(work_dir, "audio_cortado.ts")
    is_full_untouched = (
        len(segments) == 1
        and segments[0][0] <= 0.01
        and abs(segments[0][1] - total_dur) <= 0.5
    )
    if is_full_untouched:
        print("--> Sin recortes aplicados. Usando audio íntegro...")
        shutil.copy2(audio_ts, cut_ts)
        return cut_ts

    seg_files = []
    for idx, (seg_s, seg_e) in enumerate(segments, 1):
        seg_dur = seg_e - seg_s
        seg_path = os.path.join(work_dir, f"seg_{idx:02d}.ts")
        s_fmt = format_timestamp(seg_s)
        e_fmt = format_timestamp(seg_e)
        print(f"    Tramo limpio #{idx}: {s_fmt} -> {e_fmt} (duración {seg_dur:.1f}s)")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "warning",
            "-ss", s_fmt, "-t", f"{seg_dur:.3f}",
            "-i", audio_ts, "-c", "copy", seg_path,
        ]
        subprocess.run(cmd, check=True)
        seg_files.append(seg_path)

    if len(seg_files) == 1:
        shutil.move(seg_files[0], cut_ts)
    else:
        list_txt = os.path.join(work_dir, "concat.txt")
        with open(list_txt, "w", encoding="utf-8") as lf:
            for sp in seg_files:
                lf.write(f"file '{os.path.abspath(sp)}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", cut_ts],
            check=True,
        )
    return cut_ts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", required=True, help="Nombre exacto del programa")
    parser.add_argument("--start", default="00:00", help="Minuto de inicio (ej. 07:35 o 00:35:10)")
    parser.add_argument("--end", default="", help="Minuto de fin opcional (ej. 05:55:00)")
    parser.add_argument("--exclude", default="", help="Tramos a quitar por copyright separados por coma (ej. 45:12-48:30, 01:52:10-01:55:40)")
    parser.add_argument("--date", default="", help="Fecha opcional YYYY-MM-DD (por defecto la más reciente)")
    parser.add_argument("--title", default="", help="Título personalizado opcional para YouTube")
    parser.add_argument("--description", default="", help="Descripción personalizada opcional para YouTube")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--download-only", action="store_true", help="Solo generar MP4 descargable (sin subir a YouTube)")
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
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir, exist_ok=True)

    print("--> Descargando audio desde GitHub Artifacts...")
    subprocess.run(
        ["gh", "run", "download", str(run_id), "-n", art_name, "-D", work_dir],
        check=True,
    )

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

    cover_path = os.path.join(work_dir, "cover.png")
    download_cover(cover_file, cfg["covers_base_url"], cover_path)

    total_dur = probe_duration(audio_ts)
    win_start = parse_timestamp(args.start.strip() or "00:00")
    win_end = parse_timestamp(args.end.strip()) if args.end.strip() else total_dur
    win_end = min(win_end, total_dur)
    if win_end <= win_start:
        print(f"ERROR: Tiempo fin ({win_end:.1f}s) debe ser mayor al inicio ({win_start:.1f}s).", file=sys.stderr)
        sys.exit(1)

    segments = compute_keep_segments(win_start, win_end, args.exclude)
    print(f"--> Plan de corte instantáneo (Stream Copy): {len(segments)} tramo(s) limpio(s)...")
    cut_ts = build_cut_audio(audio_ts, work_dir, segments, total_dur)

    final_dur = probe_duration(cut_ts)
    print(f"--> Duración final exacta tras cortes: {final_dur:.2f}s ({format_timestamp(final_dur)})")

    final_mp4 = os.path.join(work_dir, "final_video.mp4")
    print("--> Empaquetando MP4 1080x1080 (1 FPS, BT.709, CRF 18, Opus 320 kbps)...")
    mux_mp4(cover_path, cut_ts, final_mp4, final_dur)
    mp4_mb = os.path.getsize(final_mp4) / (1024 * 1024)
    print(f"✅ MP4 listo ({mp4_mb:.1f} MB)")

    real_date = meta.get("date", art_date)
    date_label = format_date_es(real_date)

    if args.download_only:
        out_dir = "output_mp4"
        os.makedirs(out_dir, exist_ok=True)
        dest_mp4 = os.path.join(out_dir, f"{slug}__{real_date}.mp4")
        shutil.move(final_mp4, dest_mp4)
        print(f"--> Modo solo descarga activo: MP4 guardado en {dest_mp4}")
        if os.environ.get("GITHUB_ENV"):
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as gf:
                gf.write(f"MP4_ARTIFACT_NAME=MP4_{slug}__{real_date}\n")
        return

    default_title, default_desc = get_default_youtube_metadata(args.show, date_label)
    yt_title = args.title.strip() if args.title.strip() else default_title
    yt_desc = args.description.strip() if args.description.strip() else default_desc
    print(f"--> Subiendo versión limpia a YouTube ({args.privacy}): {yt_title}")
    subprocess.run(
        [
            sys.executable, os.path.join(SCRIPT_DIR, "upload_youtube.py"),
            "--file", final_mp4,
            "--title", yt_title,
            "--description", yt_desc,
            "--privacy", args.privacy,
            "--slot-index", "1",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()

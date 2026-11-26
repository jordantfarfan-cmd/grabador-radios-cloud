#!/usr/bin/env python3
"""
Consolidador de Audios y Generador de Previews Ligeros (Plan B)
- Une parte 1 + parte 2 (.ts) de cada programa en un único audio.ts continuo.
- Genera un MP3 ligero de los primeros 45 minutos (~21 MB) por programa para que el usuario
  lo escuche rápido y elija el minuto exacto de inicio.
- Prepara las carpetas listas para subir como Artifacts de GitHub.
"""

import glob
import json
import os
import shutil
import subprocess

PREVIEW_SECONDS = 45 * 60  # Primeros 45 minutos (incluye los 10 min de colchón + 35 min del show)


def safe_slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")


def main():
    os.makedirs("final_audios", exist_ok=True)
    os.makedirs("previews", exist_ok=True)

    part_dirs = sorted(glob.glob("captured/*__part_*"))
    if not part_dirs:
        print("No se encontraron grabaciones en captured/ para consolidar.")
        return

    # Agrupar por <name_slug>__<date> para coincidir exactamente con cut_and_upload.py
    grouped = {}
    logical_dates = set()
    for d in part_dirs:
        meta_path = os.path.join(d, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        name_slug = safe_slug(meta["name"])
        logical_dates.add(meta["date"])
        key = f"{name_slug}__{meta['date']}"
        grouped.setdefault(key, []).append((meta["part"], d, meta, name_slug))

    if logical_dates and os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as gf:
            gf.write(f"LOGICAL_DATE={sorted(logical_dates)[-1]}\n")

    for key, items in grouped.items():
        items.sort(key=lambda x: x[0])
        meta = items[0][2]
        slug = items[0][3]
        date_str = meta["date"]

        ts_files = []
        for part_num, d, _, _ in items:
            ts_path = os.path.join(d, f"part_{part_num}.ts")
            if os.path.isfile(ts_path) and os.path.getsize(ts_path) > 0:
                ts_files.append(ts_path)

        if not ts_files:
            print(f"⚠️ Sin audio válido para {key}")
            continue

        show_out_dir = os.path.join("final_audios", key)
        os.makedirs(show_out_dir, exist_ok=True)
        final_ts = os.path.join(show_out_dir, "audio.ts")

        if len(ts_files) == 1:
            shutil.copy2(ts_files[0], final_ts)
        else:
            list_file = os.path.join(show_out_dir, "concat.txt")
            with open(list_file, "w", encoding="utf-8") as lf:
                for tp in ts_files:
                    lf.write(f"file '{os.path.abspath(tp)}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", final_ts],
                check=True,
            )
            os.remove(list_file)

        # Guardar metadata final del audio
        with open(os.path.join(show_out_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        size_mb = os.path.getsize(final_ts) / (1024 * 1024)
        print(f"✅ Audio consolidado: {key} ({size_mb:.1f} MB)")

        # Generar Preview MP3 ligero (64 kbps, primeros 45 minutos)
        preview_mp3 = os.path.join("previews", f"{slug}__{date_str}__PREVIEW.mp3")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "warning",
                "-i", final_ts,
                "-t", str(PREVIEW_SECONDS),
                "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "2",
                preview_mp3,
            ],
            check=False,
        )
        if os.path.isfile(preview_mp3):
            p_mb = os.path.getsize(preview_mp3) / (1024 * 1024)
            print(f"   🎵 Preview generado: {os.path.basename(preview_mp3)} ({p_mb:.1f} MB)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Verifica si ya existe otro workflow run activo de record_scheduled.yml ejecutando
el mismo job (por ejemplo, lanzado por Cloudflare Cron unos minutos antes del cron
de respaldo de GitHub), para evitar dos túneles VPN simultáneos en la misma cuenta.
"""

import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

LIMA_TZ = ZoneInfo("America/Lima")
NIGHT_PIPELINE_JOBS = {"night_block_1", "night_block_2", "night_finalize"}
# SPLIT_MIN en capture_block.py es 22:50; si un cron 'schedule' arranca >= 22:45 Lima ya perdió Bloque 1.
NIGHT_BLOCK1_LATE_LIMIT_MIN = 22 * 60 + 45


def get_lima_logical_minutes(now: datetime | None = None) -> float:
    dt = now or datetime.now(LIMA_TZ)
    mins = dt.hour * 60 + dt.minute + (dt.second / 60.0)
    if dt.hour < 5:
        mins += 1440
    return mins


def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    job_name = os.environ.get("GITHUB_JOB", "")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    env_file = os.environ.get("GITHUB_ENV", "")

    already_running = False
    if event_name == "schedule" and job_name == "night_block_1":
        curr_min = get_lima_logical_minutes()
        if curr_min >= NIGHT_BLOCK1_LATE_LIMIT_MIN:
            print(
                f"⏭️ Cron 'schedule' demasiado retrasado para 'night_block_1' "
                f"(min lógico {curr_min:.1f} >= {NIGHT_BLOCK1_LATE_LIMIT_MIN}). Omitiendo ejecución parcial tardía."
            )
            already_running = True

    if not already_running and repo and run_id and job_name:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "b3tnvjwd-dup-guard",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        target_jobs = NIGHT_PIPELINE_JOBS if job_name in NIGHT_PIPELINE_JOBS else {job_name}

        try:
            url = f"https://api.github.com/repos/{repo}/actions/workflows/record_scheduled.yml/runs?per_page=10"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                runs = json.loads(resp.read().decode("utf-8")).get("workflow_runs", [])

            cur_id_num = int(run_id)
            for r in runs:
                rid = r.get("id")
                if rid == cur_id_num:
                    continue
                if r.get("status") not in ("in_progress", "queued", "waiting"):
                    continue
                # Solo ceder ante ejecuciones más antiguas (menor ID) para evitar que dos crons simultáneos se cancelen mutuamente
                if rid > cur_id_num:
                    continue

                j_url = f"https://api.github.com/repos/{repo}/actions/runs/{rid}/jobs"
                j_req = urllib.request.Request(j_url, headers=headers)
                with urllib.request.urlopen(j_req, timeout=10) as j_resp:
                    jobs = json.loads(j_resp.read().decode("utf-8")).get("jobs", [])

                for jb in jobs:
                    if jb.get("name") in target_jobs and jb.get("status") in ("in_progress", "queued"):
                        print(f"⏭️ Job '{jb.get('name')}' ya activo en run #{r.get('run_number')} (ID {rid}). Omitiendo duplicado.")
                        already_running = True
                        break
                if already_running:
                    break
        except Exception as e:
            print(f"ℹ️ No se pudo verificar duplicados ({e}); continuando ejecución normal.")

    out_file = os.environ.get("GITHUB_OUTPUT", "")
    val = "true" if already_running else "false"
    if env_file:
        with open(env_file, "a", encoding="utf-8") as gf:
            gf.write(f"ALREADY_RUNNING={val}\n")
    if out_file:
        with open(out_file, "a", encoding="utf-8") as gf:
            gf.write(f"skip={val}\n")


if __name__ == "__main__":
    main()

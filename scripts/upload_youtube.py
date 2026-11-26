#!/usr/bin/env python3
"""
Subidor Dinámico a YouTube (YouTube Data API v3)
- Soporta Balanceador de Cuota Automático entre Proyecto 1 (L-J, Dom y primeros 5 de Vie/Sáb)
  y Proyecto 2 (overflow automático para videos 6+ de Vie/Sáb o si Proyecto 1 agota cuota).
- Ambos proyectos suben al MISMO canal de YouTube en modo Privado por defecto.
"""

import argparse
import json
import os
import sys
import time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def build_youtube_service(token_json_str: str):
    info = json.loads(token_json_str)
    creds = Credentials(
        token=info.get("token"),
        refresh_token=info.get("refresh_token"),
        token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=info.get("client_id"),
        client_secret=info.get("client_secret"),
        scopes=SCOPES,
    )
    if not creds.valid or creds.expired:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def upload_with_credentials(token_json_str: str, file_path: str, title: str, description: str, privacy: str):
    youtube = build_youtube_service(token_json_str)

    body = {
        "snippet": {
            "title": title[:100],  # Límite estricto de YouTube: 100 caracteres
            "description": description,
            "categoryId": "10",  # 10 = Música
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        file_path,
        mimetype="video/mp4",
        chunksize=10 * 1024 * 1024,  # Subida resumible en bloques de 10 MB
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print(f"--> Iniciando subida a YouTube: '{title}' ({privacy})")
    response = None
    last_progress = -1
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            if pct // 10 > last_progress // 10:
                print(f"    Progreso: {pct}%")
                last_progress = pct

    video_id = response.get("id")
    print(f"--> ¡SUBIDA COMPLETADA! Video ID: {video_id}")
    print(f"--> Enlace YouTube Studio: https://studio.youtube.com/video/{video_id}/edit")
    return video_id


def main():
    parser = argparse.ArgumentParser(description="Sube un MP4 a YouTube con balanceo dinámico de cuota.")
    parser.add_argument("--file", required=True, help="Ruta al archivo MP4")
    parser.add_argument("--title", required=True, help="Título del video en YouTube")
    parser.add_argument("--description", default="Grabación automática de radio en vivo.", help="Descripción")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"], help="Estado inicial")
    parser.add_argument("--slot-index", type=int, default=1, help="Índice del video en el día (1..N)")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"ERROR: El archivo no existe: {args.file}", file=sys.stderr)
        sys.exit(1)

    t1 = os.environ.get("YT_TOKEN_1", "").strip()
    t2 = os.environ.get("YT_TOKEN_2", "").strip()

    if not t1 and not t2:
        print("ERROR: No hay credenciales YT_TOKEN_1 ni YT_TOKEN_2 configuradas.", file=sys.stderr)
        sys.exit(1)

    # Selección dinámica:
    # - Si hay Proyecto 2 y el índice del día es >= 6 (típico Vie/Sáb), usar Proyecto 2 primero para equilibrar.
    # - En caso contrario (L-J, Dom y los primeros 5 de Vie/Sáb), usar Proyecto 1.
    candidates = []
    if args.slot_index >= 6 and t2:
        candidates = [("Proyecto 2 (Overflow Vie/Sáb)", t2), ("Proyecto 1 (Principal)", t1)]
    else:
        candidates = [("Proyecto 1 (Principal)", t1)]
        if t2:
            candidates.append(("Proyecto 2 (Backup)", t2))

    # Filtrar vacíos
    candidates = [(name, tok) for name, tok in candidates if tok]

    for idx, (proj_name, token_str) in enumerate(candidates):
        try:
            print(f"--> Usando credenciales de: {proj_name} (slot #{args.slot_index})")
            upload_with_credentials(token_str, args.file, args.title, args.description, args.privacy)
            return
        except HttpError as e:
            err_text = str(e)
            is_quota = (e.resp.status == 403 and ("quotaExceeded" in err_text or "uploadLimitExceeded" in err_text))
            if is_quota and idx + 1 < len(candidates):
                print(f"--> [Aviso] Cuota diaria agotada en {proj_name}. Cambiando automáticamente al siguiente proyecto...")
                time.sleep(2)
                continue
            print(f"ERROR HTTP en {proj_name}: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR inesperado en {proj_name}: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

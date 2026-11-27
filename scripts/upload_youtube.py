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

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def build_youtube_service(token_json_str: str):
    info = json.loads(token_json_str)
    creds = Credentials(
        token=info.get("token"),
        refresh_token=info.get("refresh_token"),
        token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=info.get("client_id"),
        client_secret=info.get("client_secret"),
        scopes=info.get("scopes") or SCOPES,
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


def find_playlist_id(youtube, target_title: str) -> str | None:
    target_norm = target_title.strip()
    page_token = None
    while True:
        req = youtube.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=page_token)
        res = req.execute()
        for item in res.get("items", []):
            title = item.get("snippet", {}).get("title", "").strip()
            if title == target_norm:
                return item["id"]
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return None


def add_video_to_playlist(video_id: str, playlist_title: str, tokens: list[tuple[str, str]]):
    clean_pl = (playlist_title or "").strip()
    if not clean_pl or clean_pl.upper() == "NONE":
        return

    # Buscar un token con permiso youtube.force-ssl o youtube completo (ej. YT_PLAYLIST_TOKEN o YT_TOKEN_1)
    ordered = []
    extra = os.environ.get("YT_PLAYLIST_TOKEN", "").strip()
    if extra:
        ordered.append(("YT_PLAYLIST_TOKEN", extra))
    ordered.extend(tokens)

    eligible = []
    for name, tok_str in ordered:
        try:
            scopes = json.loads(tok_str).get("scopes") or []
        except Exception:
            scopes = []
        if any(s.endswith("/auth/youtube.force-ssl") or s.endswith("/auth/youtube") for s in scopes):
            eligible.append((name, tok_str))

    if not eligible:
        print(f"::warning::No se encontró ningún YT_TOKEN con permiso 'youtube.force-ssl' para añadir a la playlist '{clean_pl}'. El video sí se subió bien.")
        return

    for name, tok_str in eligible:
        try:
            yt = build_youtube_service(tok_str)
            pl_id = find_playlist_id(yt, clean_pl)
            if not pl_id:
                print(f"::warning::No se encontró la playlist '{clean_pl}' en el canal con {name}.")
                return
            yt.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": pl_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
            print(f"--> ✅ Video añadido automáticamente a la playlist: {clean_pl}")
            return
        except Exception as e:
            print(f"--> [Aviso] Falló añadir a playlist con {name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Sube un MP4 a YouTube con balanceo dinámico de cuota.")
    parser.add_argument("--file", required=True, help="Ruta al archivo MP4")
    parser.add_argument("--title", required=True, help="Título del video en YouTube")
    parser.add_argument("--description", default="Grabación automática de radio en vivo.", help="Descripción")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"], help="Estado inicial")
    parser.add_argument("--playlist", default="", help="Nombre exacto de la playlist de YouTube (opcional)")
    parser.add_argument("--slot-index", type=int, default=1, help="Índice del video en el día (1..N)")
    parser.add_argument("--out-video-id", default="", help="Ruta opcional para guardar el Video ID subido")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"ERROR: El archivo no existe: {args.file}", file=sys.stderr)
        sys.exit(1)

    # Descubrir dinámicamente YT_TOKEN_1 .. YT_TOKEN_10 configurados en Secrets
    tokens = []
    for i in range(1, 11):
        val = os.environ.get(f"YT_TOKEN_{i}", "").strip()
        if val:
            tokens.append((f"Proyecto {i}", val))

    if not tokens:
        print("ERROR: No hay credenciales YT_TOKEN_1..N configuradas.", file=sys.stderr)
        sys.exit(1)

    # Distribuir carga en bloques de ~5 subidas por proyecto y rotar por todos si se agota la cuota
    start_idx = ((max(1, args.slot_index) - 1) // 5) % len(tokens)
    candidates = tokens[start_idx:] + tokens[:start_idx]

    for idx, (proj_name, token_str) in enumerate(candidates):
        try:
            print(f"--> Usando credenciales de: {proj_name} (slot #{args.slot_index})")
            video_id = upload_with_credentials(token_str, args.file, args.title, args.description, args.privacy)
            if video_id and args.out_video_id.strip():
                out_path = os.path.abspath(args.out_video_id.strip())
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as vf:
                    vf.write(f"{video_id}\n")
            if video_id and args.playlist.strip():
                add_video_to_playlist(video_id, args.playlist, tokens)
            return
        except HttpError as e:
            err_text = str(e)
            is_quota = (
                e.resp.status in (403, 429)
                and any(k in err_text for k in ("quotaExceeded", "uploadLimitExceeded", "dailyLimitExceeded", "rateLimitExceeded"))
            )
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

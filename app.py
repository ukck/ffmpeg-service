import os
import uuid
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

app = FastAPI(title="FFmpeg MP3 Converter", version="1.0.0")
TMP_DIR = Path("/tmp/ffmpeg_api")
TMP_DIR.mkdir(parents=True, exist_ok=True)

def run_ffmpeg_to_mp3(inp_path: Path, bitrate: str, samplerate: int, channels: int) -> Path:
    out_path = TMP_DIR / f"{uuid.uuid4().hex}.mp3"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-y", "-i", str(inp_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", bitrate,
        "-ar", str(samplerate),
        "-ac", str(channels),
        str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True)
        return out_path
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=400, detail=f"ffmpeg failed: {e}")
    finally:
        if inp_path.exists():
            inp_path.unlink(missing_ok=True)

def stream_file_delete_after(path: Path):
    def _iterfile():
        with open(path, "rb") as f:
            try:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
    return _iterfile()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/convert")
async def convert(
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None),
    bitrate: str = Form(default="192k"),
    samplerate: int = Form(default=44100),
    channels: int = Form(default=2),
    filename: Optional[str] = Form(default=None)
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="必须提供 file 或 url")
    if file and url:
        raise HTTPException(status_code=400, detail="file 与 url 只能二选一")

    in_path = TMP_DIR / f"{uuid.uuid4().hex}.input"
    try:
        if file:
            size = 0
            with open(in_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 200 * 1024 * 1024:
                        raise HTTPException(status_code=413, detail="文件过大")
                    f.write(chunk)
        else:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise HTTPException(status_code=400, detail="仅支持 http/https URL")
            timeout = httpx.Timeout(connect=10, read=60, write=60, pool=10)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                async with client.stream("GET", url) as r:
                    r.raise_for_status()
                    size = 0
                    with open(in_path, "wb") as f:
                        async for chunk in r.aiter_bytes():
                            size += len(chunk)
                            if size > 200 * 1024 * 1024:
                                raise HTTPException(status_code=413, detail="远程文件过大")
                            f.write(chunk)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"下载失败: {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"下载失败: {str(e)}")

    out_path = run_ffmpeg_to_mp3(in_path, bitrate, samplerate, channels)
    base = filename or "converted"
    dispo = f'attachment; filename="{base}.mp3"'

    return StreamingResponse(
        stream_file_delete_after(out_path),
        media_type="audio/mpeg",
        headers={"Content-Disposition": dispo}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

import os
import uuid
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="FFmpeg Media Converter", version="0.2.0")
TMP_DIR = Path("/tmp/ffmpeg_api")
TMP_DIR.mkdir(parents=True, exist_ok=True)

class ConversionType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"

# Conversion configurations
CONVERSION_CONFIGS = {
    "mp3": {
        "type": ConversionType.AUDIO,
        "extension": ".mp3",
        "media_type": "audio/mpeg",
        "ffmpeg_params": [
            "-vn",
            "-acodec", "libmp3lame",
        ]
    },
    "mp4": {
        "type": ConversionType.VIDEO,
        "extension": ".mp4",
        "media_type": "video/mp4",
        "ffmpeg_params": [
            "-vcodec", "libx264",
            "-acodec", "aac",
        ]
    },
    "jpg": {
        "type": ConversionType.IMAGE,
        "extension": ".jpg",
        "media_type": "image/jpeg",
        "ffmpeg_params": [
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
            "-q:v", "2",  # JPEG quality
        ]
    }
}

def run_ffmpeg_conversion(
    inp_path: Path, 
    output_format: str,
    **kwargs
) -> Path:
    """Run FFmpeg conversion based on the output format."""
    if output_format not in CONVERSION_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unsupported output format: {output_format}")
    
    config = CONVERSION_CONFIGS[output_format]
    out_path = TMP_DIR / f"{uuid.uuid4().hex}{config['extension']}"
    
    # Base command
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-y", "-i", str(inp_path),
    ]
    
    # Add format-specific parameters
    cmd.extend(config["ffmpeg_params"])
    
    # Add format-specific options
    if output_format == "mp3":
        bitrate = kwargs.get("bitrate", "192k")
        samplerate = kwargs.get("samplerate", 44100)
        channels = kwargs.get("channels", 2)
        cmd.extend([
            "-b:a", bitrate,
            "-ar", str(samplerate),
            "-ac", str(channels),
        ])
    elif output_format == "mp4":
        # Video quality settings
        cmd.extend([
            "-preset", "medium",
            "-crf", "23",
        ])
    elif output_format == "jpg":
        # Image quality already set in ffmpeg_params
        pass
    
    # Output file
    cmd.append(str(out_path))
    
    try:
        logger.info(f"开始转换: {inp_path} -> {out_path} (格式: {output_format})")
        subprocess.run(cmd, check=True)
        logger.info(f"转换成功: {out_path}")
        return out_path
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg转换失败: {e}, 命令: {' '.join(cmd)}")
        raise HTTPException(status_code=400, detail=f"ffmpeg failed: {e}")
    finally:
        if inp_path.exists():
            inp_path.unlink(missing_ok=True)
            logger.info(f"已删除输入文件: {inp_path}")

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
                    if path.exists():
                        path.unlink()
                        logger.info(f"已删除临时文件: {path}")
                except OSError as e:
                    logger.warning(f"删除临时文件失败: {path}, 错误: {e}")
                except Exception as e:
                    logger.error(f"删除临时文件时发生未知错误: {path}, 错误: {e}")
    return _iterfile()

async def handle_file_upload_or_url(
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None)
) -> Path:
    """Handle file upload or URL download and save to temporary file."""
    if not file and not url:
        raise HTTPException(status_code=400, detail="必须提供 file 或 url")
    if file and url:
        raise HTTPException(status_code=400, detail="file 与 url 只能二选一")

    in_path = TMP_DIR / f"{uuid.uuid4().hex}.input"
    try:
        if file:
            logger.info(f"开始上传文件: {file.filename}")
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
            logger.info(f"文件上传完成: {file.filename}, 大小: {size} bytes")
        else:
            if not (url.startswith("http://") or url.startswith("https://")):
                raise HTTPException(status_code=400, detail="仅支持 http/https URL")
            logger.info(f"开始下载远程文件: {url}")
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
            logger.info(f"远程文件下载完成: {url}, 大小: {size} bytes")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"下载失败: {e.response.status_code}")
    except httpx.TimeoutError as e:
        raise HTTPException(status_code=408, detail=f"下载超时: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"下载失败: {str(e)}")
    
    return in_path

@app.get("/")
def root():
    return {
        "message": "FFmpeg Media Converter API",
        "version": app.version,
        "description": "Convert audio, video, and images using FFmpeg.",
        "endpoints": {
            "GET /": "This page",
            "GET /health": "Health check",
            "POST /mp3": "Convert to MP3",
            "POST /mp4": "Convert to MP4",
            "POST /jpg": "Convert to JPG"
        },
        "examples": {
            "convert_to_mp3_from_file": "curl -X POST http://localhost:8000/mp3 -F \"file=@input.wav\" -F \"bitrate=320k\" -o output.mp3",
            "convert_to_mp3_from_url": "curl -X POST http://localhost:8000/mp3 -F \"url=https://example.com/audio.wav\" -o output.mp3",
            "convert_to_mp4_from_file": "curl -X POST http://localhost:8000/mp4 -F \"file=@input.avi\" -o output.mp4",
            "convert_to_jpg_from_url": "curl -X POST http://localhost:8000/jpg -F \"url=https://example.com/image.png\" -o output.jpg"
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/mp3")
async def convert_to_mp3(
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None),
    bitrate: str = Form(default="192k"),
    samplerate: int = Form(default=44100),
    channels: int = Form(default=2),
    filename: Optional[str] = Form(default=None)
):
    """Convert audio file to MP3."""
    in_path = await handle_file_upload_or_url(file, url)
    out_path = run_ffmpeg_conversion(
        in_path, 
        "mp3",
        bitrate=bitrate,
        samplerate=samplerate,
        channels=channels
    )
    base = filename or "converted"
    dispo = f'attachment; filename="{base}.mp3"'

    return StreamingResponse(
        stream_file_delete_after(out_path),
        media_type="audio/mpeg",
        headers={"Content-Disposition": dispo}
    )

@app.post("/mp4")
async def convert_to_mp4(
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None),
    filename: Optional[str] = Form(default=None)
):
    """Convert video file to MP4."""
    in_path = await handle_file_upload_or_url(file, url)
    out_path = run_ffmpeg_conversion(in_path, "mp4")
    base = filename or "converted"
    dispo = f'attachment; filename="{base}.mp4"'

    return StreamingResponse(
        stream_file_delete_after(out_path),
        media_type="video/mp4",
        headers={"Content-Disposition": dispo}
    )

@app.post("/jpg")
async def convert_to_jpg(
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None),
    filename: Optional[str] = Form(default=None)
):
    """Convert image file to JPG."""
    in_path = await handle_file_upload_or_url(file, url)
    out_path = run_ffmpeg_conversion(in_path, "jpg")
    base = filename or "converted"
    dispo = f'attachment; filename="{base}.jpg"'

    return StreamingResponse(
        stream_file_delete_after(out_path),
        media_type="image/jpeg",
        headers={"Content-Disposition": dispo}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

import ipaddress
import socket
from urllib.parse import urlparse, unquote

import httpx
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Video Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

HTML = """
<!DOCTYPE html>
<html lang="my">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Video Downloader</title>
<style>
body{font-family:Arial,sans-serif;background:#101522;color:white;
padding:24px;max-width:650px;margin:40px auto}
.card{background:#1c2538;padding:24px;border-radius:16px}
input,button{box-sizing:border-box;width:100%;padding:14px;
margin-top:12px;border-radius:9px;font-size:16px}
input{background:#101522;color:white;border:1px solid #475569}
button{background:#37b7a5;color:#071b20;border:0;font-weight:bold}
p{color:#cbd5e1;line-height:1.6}
</style>
</head>
<body>
<div class="card">
<h2>🎬 Video Downloader</h2>
<p>ခွင့်ပြုထားသော တိုက်ရိုက် MP4 လင့်ခ်ကို ထည့်ပါ။</p>
<form action="/download" method="post">
<input name="url" type="url" placeholder="https://example.com/video.mp4"
required>
<button type="submit">MP4 Download</button>
</form>
<p>Hongguo Share Link များကို တိုက်ရိုက် MP4 အဖြစ်
ပြောင်းပေးနိုင်ကြောင်း အာမမခံပါ။</p>
</div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML


def validate_url(url: str):
    parsed = urlparse(url.strip())

    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("HTTPS လင့်ခ်ကို အသုံးပြုပါ။")

    host = parsed.hostname.lower()

    if host in ("localhost",) or host.endswith(".local"):
        raise ValueError("ဒီလင့်ခ်ကို အသုံးမပြုနိုင်ပါ။")

    try:
        addresses = socket.getaddrinfo(
            host, 443, type=socket.SOCK_STREAM
        )
        for item in addresses:
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                raise ValueError("Public HTTPS URL ကို အသုံးပြုပါ။")
    except socket.gaierror:
        raise ValueError("Hostname ကို ရှာမတွေ့ပါ။")

    return parsed


@app.post("/download")
async def download(url: str = Form(...)):
    try:
        parsed = validate_url(url)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)

    filename = unquote(parsed.path.rsplit("/", 1)[-1])
    if not filename.lower().endswith(".mp4"):
        return HTMLResponse(
            "တိုက်ရိုက် .mp4 URL ဖြစ်ရပါမယ်။",
            status_code=400,
        )

    async def stream_video():
        timeout = httpx.Timeout(30, read=120)
        async with httpx.AsyncClient(
            follow_redirects=False, timeout=timeout
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                content_type = response.headers.get(
                    "content-type", ""
                )
                if "video/" not in content_type and (
                    "octet-stream" not in content_type
                ):
                    raise ValueError("MP4 ဖိုင်မဟုတ်နိုင်ပါ။")

                async for chunk in response.aiter_bytes(1024 * 256):
                    yield chunk

    safe_filename = "".join(
        c for c in filename if c.isalnum() or c in "._-"
    ) or "video.mp4"

    return StreamingResponse(
        stream_video(),
        media_type="video/mp4",
        headers={
            "Content-Disposition":
                f'attachment; filename="{safe_filename}"'
        },
    )

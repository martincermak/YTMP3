"""
Stáhne závislosti do složky deps/, odkud je zabalí instalátor (installer.iss):
  yt-dlp.exe, ffmpeg.exe, ffprobe.exe, deno.exe

Použití:  python fetch_deps.py [--force]
"""
import io
import os
import sys
import urllib.request
import zipfile

try:  # systémové certifikáty (firemní proxy apod.)
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass

DEPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deps")

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_URL = (
    "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/"
    "ffmpeg-master-latest-win64-gpl.zip"
)
DENO_URL = (
    "https://github.com/denoland/deno/releases/latest/download/"
    "deno-x86_64-pc-windows-msvc.zip"
)

REQUIRED = ("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe", "deno.exe")


def download(url):
    print(f"Stahuji {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ytmp3-build"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def extract(data, wanted):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            base = os.path.basename(name).lower()
            if base in wanted:
                with z.open(name) as src, open(os.path.join(DEPS_DIR, base), "wb") as dst:
                    dst.write(src.read())
                print(f"  -> {base}", flush=True)


def main():
    force = "--force" in sys.argv
    os.makedirs(DEPS_DIR, exist_ok=True)

    def have(*names):
        return all(os.path.isfile(os.path.join(DEPS_DIR, n)) for n in names) and not force

    if not have("yt-dlp.exe"):
        with open(os.path.join(DEPS_DIR, "yt-dlp.exe"), "wb") as f:
            f.write(download(YTDLP_URL))
    if not have("ffmpeg.exe", "ffprobe.exe"):
        extract(download(FFMPEG_URL), {"ffmpeg.exe", "ffprobe.exe"})
    if not have("deno.exe"):
        extract(download(DENO_URL), {"deno.exe"})

    missing = [n for n in REQUIRED if not os.path.isfile(os.path.join(DEPS_DIR, n))]
    if missing:
        print(f"CHYBA: chybí {', '.join(missing)}", file=sys.stderr)
        return 1
    for n in REQUIRED:
        print(f"{n}: {os.path.getsize(os.path.join(DEPS_DIR, n)) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

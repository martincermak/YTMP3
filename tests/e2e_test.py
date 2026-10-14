"""
E2E test (Windows): nainstalovaná appka stáhne zdroj a vyrobí z něj MP3.

Ověřuje, že:
  1. instalace obsahuje všechny závislosti (yt-dlp, ffmpeg, ffprobe, deno),
  2. `YTMP3.exe --cli` doběhne s kódem 0,
  3. vznikne MP3 s velikostí > 0 a platnou hlavičkou (ID3 nebo MPEG sync).

Zdroje (--source):
  youtube  vlastní neveřejné (unlisted) 10s video, ID 8nNxyoJnZXM - výchozí
  local    3 s video vyrobené nainstalovaným ffmpeg a vystavené na lokálním HTTP
           serveru; nezávisí na žádné externí službě (deterministické)

Použití:
  python tests/e2e_test.py [cesta\\k\\YTMP3.exe] [--source youtube|local]
Výchozí cesta: %LOCALAPPDATA%\\Programs\\YTMP3\\YTMP3.exe (nebo proměnná YTMP3_EXE).
URL pro youtube jde změnit proměnnou YTMP3_TEST_URL.

Návratové kódy: 0 = OK, 1 = chyba, 2 = nerozhodnuto (YouTube blokuje IP jako bota;
s YTMP3_E2E_STRICT=1 se i tohle bere jako chyba).
"""
import argparse
import functools
import glob
import http.server
import os
import subprocess
import sys
import tempfile
import threading

# Windows runner má konzoli v cp1252 - česká diakritika by shodila print()
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

YOUTUBE_URL = os.environ.get("YTMP3_TEST_URL", "https://www.youtube.com/watch?v=8nNxyoJnZXM")
DEPS = ("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe", "deno.exe")
TIMEOUT = 300
BOT_MARKERS = ("not a bot", "sign in to confirm")


def read_log(path):
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    return ""


def fail(msg, log_path=None, code=1):
    log = read_log(log_path)
    if log:
        print("----- ytmp3-cli.log -----")
        print(log)
        print("-------------------------")
    print(f"FAIL: {msg}")
    sys.exit(code)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def make_local_source(app_dir, serve_dir):
    """Vyrobí sample.mp4 ffmpegem z instalace a vystaví ho na http://127.0.0.1:PORT/."""
    sample = os.path.join(serve_dir, "sample.mp4")
    try:
        r = subprocess.run(
            [
                os.path.join(app_dir, "ffmpeg.exe"), "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:d=3:r=10",
                "-c:a", "aac", "-c:v", "mpeg4", "-shortest", sample,
            ],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        fail(f"ffmpeg z instalace nejde spustit: {e}")
    if r.returncode != 0 or not os.path.isfile(sample):
        fail(f"ffmpeg z instalace nevyrobil testovací video: {r.stderr.strip()}")
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_QuietHandler, directory=serve_dir)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/sample.mp4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", nargs="?")
    ap.add_argument("--source", choices=("youtube", "local"), default="youtube")
    args = ap.parse_args()

    exe = (
        args.exe
        or os.environ.get("YTMP3_EXE")
        or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "YTMP3", "YTMP3.exe")
    )
    if not os.path.isfile(exe):
        fail(f"aplikace nenalezena: {exe}")

    app_dir = os.path.dirname(os.path.abspath(exe))
    missing = [d for d in DEPS if not os.path.isfile(os.path.join(app_dir, d))]
    if missing:
        fail(f"v instalaci chybí: {', '.join(missing)}")
    print(f"OK: instalace obsahuje {', '.join(DEPS)}")

    with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as serve_dir:
        server = None
        if args.source == "local":
            server, url = make_local_source(app_dir, serve_dir)
        else:
            url = YOUTUBE_URL

        log_path = os.path.join(out, "ytmp3-cli.log")
        print(f"[{args.source}] stahuji {url} ...", flush=True)
        try:
            try:
                r = subprocess.run([exe, "--cli", url, out, "128"], timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                fail(f"timeout po {TIMEOUT} s", log_path)
        finally:
            if server:
                server.shutdown()

        if r.returncode != 0:
            log = read_log(log_path).lower()
            if (
                args.source == "youtube"
                and any(m in log for m in BOT_MARKERS)
                and os.environ.get("YTMP3_E2E_STRICT") != "1"
            ):
                print(read_log(log_path))
                print("INCONCLUSIVE: YouTube blokuje tuhle IP adresu (bot check); "
                      "test nelze vyhodnotit.")
                sys.exit(2)
            fail(f"YTMP3.exe skončil s kódem {r.returncode}", log_path)

        mp3s = glob.glob(os.path.join(out, "**", "*.mp3"), recursive=True)
        if not mp3s:
            fail("nevznikl žádný .mp3 soubor", log_path)

        for path in mp3s:
            size = os.path.getsize(path)
            if size <= 0:
                fail(f"prázdný soubor: {path}", log_path)
            with open(path, "rb") as f:
                head = f.read(3)
            if not (head == b"ID3" or head[:1] == b"\xff"):
                fail(f"soubor nevypadá jako MP3 (hlavička {head!r}): {path}", log_path)
            print(f"OK: {os.path.basename(path)} ({size} B)")

    print("E2E TEST PASSED")


if __name__ == "__main__":
    main()

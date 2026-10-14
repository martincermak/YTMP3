"""
Jádro YT MP3 bez GUI: hledání nástrojů, příkazová řádka yt-dlp, stahování
závislostí, srozumitelné chybové hlášky, nastavení a headless režim (--cli).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

try:  # systémové certifikáty (firemní proxy / antivir s kontrolou HTTPS)
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001
    pass

APP_DIR = os.path.dirname(
    sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PROG_PREFIX = "[PROG]"

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_URL = (
    "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/"
    "ffmpeg-master-latest-win64-gpl.zip"
)
DENO_URL = (
    "https://github.com/denoland/deno/releases/latest/download/"
    "deno-x86_64-pc-windows-msvc.zip"
)


# ---------------------------------------------------------------- nástroje
def find_tool(name):
    local = os.path.join(APP_DIR, name + ".exe")
    if os.path.isfile(local):
        return local
    return shutil.which(name)


def parse_urls(text):
    """Vytáhne z textu http(s) odkazy (oddělené mezerou / novým řádkem), bez duplicit."""
    urls = []
    for tok in re.split(r"\s+", text or ""):
        if re.match(r"^https?://\S+$", tok, re.I) and tok not in urls:
            urls.append(tok)
    return urls


def build_command(ytdlp, url, outdir, quality, playlist, thumb):
    """Sestaví příkazovou řádku yt-dlp (sdílí GUI i headless režim)."""
    tmpl = (
        "%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s"
        if playlist else "%(title)s.%(ext)s"
    )
    cmd = [
        ytdlp, "-x", "--audio-format", "mp3", "--audio-quality", f"{quality}K",
        "-P", outdir, "-o", tmpl,
        "--yes-playlist" if playlist else "--no-playlist",
        "--newline", "--encoding", "utf-8", "--windows-filenames",
        "--progress-template",
        f"download:{PROG_PREFIX}%(progress._percent_str)s|%(progress._speed_str)s"
        "|%(progress._eta_str)s|%(info.duration_string)s|%(info.title)s",
    ]
    if thumb:
        cmd += ["--embed-metadata", "--embed-thumbnail", "--convert-thumbnails", "jpg"]
    if os.path.isfile(os.path.join(APP_DIR, "ffmpeg.exe")):
        cmd += ["--ffmpeg-location", APP_DIR]
    cmd.append(url)
    return cmd


DEFAULT_ERROR_TITLE = "Stažení se nepovedlo"


def friendly_error(text):
    """Přeloží technický výpis yt-dlp na (nadpis, srozumitelná zpráva)."""
    t = (text or "").lower()

    def has(*needles):
        return any(n in t for n in needles)

    if has("not a bot", "sign in to confirm you"):
        return ("YouTube žádá ověření",
                "YouTube teď blokuje stahování z tvé sítě. Zkus to později nebo aktualizuj yt-dlp.")
    if has("confirm your age", "age-restricted", "age restricted"):
        return ("Video je omezené věkem", "Ke stažení je potřeba přihlášení na YouTube.")
    if has("private video", "video unavailable", "this video is not available",
           "video is not available", "has been removed", "this video has been",
           "not made this video available in your country"):
        return ("Video není dostupné", "Je soukromé, smazané nebo omezené ve tvé zemi.")
    if has("unsupported url"):
        return ("Tohle není odkaz na video", "Zkontroluj, že odkaz míří na video z YouTube.")
    if has("certificate_verify_failed", "ssl:", "certificate verify"):
        return ("Chyba zabezpečeného připojení",
                "Síť pravděpodobně kontroluje HTTPS (firemní proxy nebo antivir).")
    if has("ffprobe and ffmpeg not found", "ffmpeg not found", "ffprobe not found"):
        return ("Chybí ffmpeg", "Přeinstaluj aplikaci, nebo vedle ní dej ffmpeg.exe a ffprobe.exe.")
    if has("unable to download", "getaddrinfo", "name resolution", "timed out",
           "connection refused", "failed to establish", "network is unreachable",
           "urlopen error", "no address associated", "connection reset"):
        return ("Bez připojení", "Zkontroluj připojení k internetu a zkus to znovu.")
    return (DEFAULT_ERROR_TITLE, "Podrobnosti najdeš v „Podrobnostech“, nebo zkus aktualizovat yt-dlp.")


# ------------------------------------------------- stahování závislostí
def download_file(url, dest, label, report):
    part = dest + ".part"
    last = {"pct": -1}

    def hook(blocks, bsize, total):
        if total > 0:
            pct = int(min(100, blocks * bsize * 100 / total))
            if pct != last["pct"]:
                last["pct"] = pct
                report("status", f"Stahuji {label}… {pct} %")

    urllib.request.urlretrieve(url, part, hook)
    os.replace(part, dest)


def _extract(zpath, wanted):
    found = set()
    try:
        with zipfile.ZipFile(zpath) as z:
            for name in z.namelist():
                base = os.path.basename(name).lower()
                if base in wanted:
                    with z.open(name) as src, open(os.path.join(APP_DIR, base), "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found.add(base)
    finally:
        try:
            os.remove(zpath)
        except OSError:
            pass
    missing = set(wanted) - found
    if missing:
        raise RuntimeError(f"v archivu chybí: {', '.join(sorted(missing))}")


def ensure_ytdlp(report):
    if find_tool("yt-dlp"):
        return
    report("log", "Stahuji yt-dlp.exe…")
    download_file(YTDLP_URL, os.path.join(APP_DIR, "yt-dlp.exe"), "yt-dlp", report)


def ensure_ffmpeg(report):
    if find_tool("ffmpeg") and find_tool("ffprobe"):
        return
    report("log", "Stahuji ffmpeg (cca 150 MB, jen jednou)…")
    zpath = os.path.join(APP_DIR, "ffmpeg.zip")
    download_file(FFMPEG_URL, zpath, "ffmpeg", report)
    report("status", "Rozbaluji ffmpeg…")
    _extract(zpath, {"ffmpeg.exe", "ffprobe.exe"})


def ensure_deno(report):
    if find_tool("deno"):
        return
    report("log", "Stahuji Deno (JS runtime pro YouTube, jen jednou)…")
    zpath = os.path.join(APP_DIR, "deno.zip")
    download_file(DENO_URL, zpath, "Deno", report)
    report("status", "Rozbaluji Deno…")
    _extract(zpath, {"deno.exe"})


def ensure_all(report):
    """Doplní chybějící závislosti (v instalaci by měly být všechny už přibalené)."""
    ensure_ytdlp(report)
    ensure_ffmpeg(report)
    ensure_deno(report)


def tool_version(exe):
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        out = (r.stdout or "").strip().splitlines()
        return out[0].strip() if r.returncode == 0 and out else None
    except (OSError, subprocess.SubprocessError):
        return None


def update_ytdlp(report):
    """Spustí `yt-dlp -U`, výstup posílá do `report("log", …)`; vrátí novou verzi (nebo None)."""
    ensure_ytdlp(report)
    exe = find_tool("yt-dlp")
    proc = subprocess.Popen(
        [exe, "-U"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
    )
    for line in proc.stdout:
        if line.strip():
            report("log", line.rstrip())
    proc.wait()
    return tool_version(exe)


# --------------------------------------------------------------- nastavení
def _default_outdir():
    return os.path.join(os.path.expanduser("~"), "Music")


def settings_path():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "YTMP3", "settings.json")


def default_settings():
    return {"quality": "192", "outdir": _default_outdir(), "playlist": False,
            "thumb": True, "details": False}


def load_settings():
    s = default_settings()
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            s.update({k: v for k, v in data.items() if k in s})
    except (OSError, ValueError):
        pass
    if s["quality"] not in ("128", "192", "256", "320"):
        s["quality"] = "192"
    return s


def save_settings(s):
    try:
        path = settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------- headless režim
def run_cli(args):
    """Headless režim pro testy: YTMP3.exe --cli URL SLOZKA [KVALITA].

    Nic se nestahuje automaticky - chybějící závislost = chyba (test tak ověří,
    že instalátor všechno obsahuje). Výstup jde do SLOZKA\\ytmp3-cli.log.
    """
    if len(args) < 2:
        return 64
    url, outdir = args[0], args[1]
    quality = args[2] if len(args) > 2 else "192"
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "ytmp3-cli.log"), "w", encoding="utf-8") as log:
        tools = {n: find_tool(n) for n in ("yt-dlp", "ffmpeg", "ffprobe", "deno")}
        for name, path in tools.items():
            log.write(f"{name}: {path}\n")
        missing = [n for n, p in tools.items() if not p]
        if missing:
            log.write(f"CHYBA: chybí {', '.join(missing)}\n")
            return 2
        log.flush()
        cmd = build_command(tools["yt-dlp"], url, outdir, quality, False, True)
        if os.environ.get("YTMP3_VERBOSE"):
            cmd.insert(1, "-v")
        proc = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=NO_WINDOW,
        )
        return proc.returncode

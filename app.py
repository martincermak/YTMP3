"""
YT MP3 – jednoduchý Windows GUI wrapper kolem yt-dlp.

Požadavky za běhu:
  - yt-dlp.exe  (pokud chybí, appka si ho umí stáhnout sama)
  - ffmpeg.exe  (vedle appky nebo v PATH; např. `winget install Gyan.FFmpeg`)
"""
import os
import queue
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = os.path.dirname(
    sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
)
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_URL = (
    "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/"
    "ffmpeg-master-latest-win64-gpl.zip"
)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PROG_PREFIX = "[PROG]"


def find_tool(name):
    local = os.path.join(APP_DIR, name + ".exe")
    if os.path.isfile(local):
        return local
    return shutil.which(name)


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.proc = None
        self.cancelled = False
        self.worker = None

        root.title("YT MP3")
        root.geometry("640x520")
        root.minsize(520, 420)

        self.outdir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Music"))
        self.quality = tk.StringVar(value="192")
        self.playlist = tk.BooleanVar(value=False)
        self.thumb = tk.BooleanVar(value=True)

        self._build_ui()
        self.root.after(100, self._poll)
        self._check_tools()

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=6, pady=6)

        ttk.Label(main, text="URL (jedna na řádek):").pack(anchor="w", **pad)
        self.urls = tk.Text(main, height=4, wrap="none")
        self.urls.pack(fill="x", **pad)

        row = ttk.Frame(main)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Složka:").pack(side="left")
        ttk.Entry(row, textvariable=self.outdir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Vybrat…", command=self._pick_dir).pack(side="left")

        opts = ttk.Frame(main)
        opts.pack(fill="x", **pad)
        ttk.Label(opts, text="Kvalita (kbps):").pack(side="left")
        ttk.Combobox(
            opts, textvariable=self.quality, values=["128", "192", "256", "320"],
            width=5, state="readonly",
        ).pack(side="left", padx=6)
        ttk.Checkbutton(opts, text="Celý playlist", variable=self.playlist).pack(side="left", padx=10)
        ttk.Checkbutton(opts, text="Obrázek alba + metadata", variable=self.thumb).pack(side="left", padx=10)

        btns = ttk.Frame(main)
        btns.pack(fill="x", **pad)
        self.btn_dl = ttk.Button(btns, text="Stáhnout", command=self._start)
        self.btn_dl.pack(side="left")
        self.btn_cancel = ttk.Button(btns, text="Zrušit", command=self._cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=6)
        self.btn_update = ttk.Button(btns, text="Aktualizovat yt-dlp", command=self._update)
        self.btn_update.pack(side="right")

        self.bar = ttk.Progressbar(main, maximum=100)
        self.bar.pack(fill="x", **pad)
        self.status = ttk.Label(main, text="Připraveno")
        self.status.pack(anchor="w", **pad)

        logf = ttk.Frame(main)
        logf.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(logf, height=10, state="disabled", wrap="word")
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get())
        if d:
            self.outdir.set(d)

    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy):
        self.btn_dl.configure(state="disabled" if busy else "normal")
        self.btn_update.configure(state="disabled" if busy else "normal")
        self.btn_cancel.configure(state="normal" if busy else "disabled")

    # ---------- Tools ----------
    def _check_tools(self):
        if not (find_tool("ffmpeg") and find_tool("ffprobe")):
            self._log("ffmpeg/ffprobe nenalezen – stáhne se automaticky při prvním stahování.")
        if not find_tool("yt-dlp"):
            self._log("yt-dlp.exe nenalezen – stáhne se automaticky při prvním stahování.")

    def _download_file(self, url, dest, label):
        """Stáhne soubor s progress barem; zapisuje přes .part a pak přejmenuje."""
        part = dest + ".part"
        last = {"pct": -1}

        def hook(blocks, bsize, total):
            if total > 0:
                pct = int(min(100, blocks * bsize * 100 / total))
                if pct != last["pct"]:
                    last["pct"] = pct
                    self.q.put(("bar", pct))
                    self.q.put(("status", f"Stahuji {label}… {pct} %"))

        urllib.request.urlretrieve(url, part, hook)
        os.replace(part, dest)
        self.q.put(("bar", 0))

    def _ensure_ytdlp(self):
        path = find_tool("yt-dlp")
        if path:
            return path
        dest = os.path.join(APP_DIR, "yt-dlp.exe")
        self.q.put(("log", "Stahuji yt-dlp.exe…"))
        self._download_file(YTDLP_URL, dest, "yt-dlp")
        self.q.put(("log", f"yt-dlp uložen do {dest}"))
        return dest

    def _ensure_ffmpeg(self):
        if find_tool("ffmpeg") and find_tool("ffprobe"):
            return
        self.q.put(("log", "Stahuji ffmpeg (cca 150 MB, jen jednou)…"))
        zpath = os.path.join(APP_DIR, "ffmpeg.zip")
        self._download_file(FFMPEG_URL, zpath, "ffmpeg")
        self.q.put(("status", "Rozbaluji ffmpeg…"))
        try:
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    base = os.path.basename(name).lower()
                    if base in ("ffmpeg.exe", "ffprobe.exe"):
                        with z.open(name) as src, open(os.path.join(APP_DIR, base), "wb") as dst:
                            shutil.copyfileobj(src, dst)
        finally:
            try:
                os.remove(zpath)
            except OSError:
                pass
        self.q.put(("log", f"ffmpeg a ffprobe uloženy do {APP_DIR}"))

    # ---------- Actions ----------
    def _start(self):
        urls = [u.strip() for u in self.urls.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showinfo("YT MP3", "Vlož aspoň jednu URL.")
            return
        outdir = self.outdir.get().strip()
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("YT MP3", f"Složku nelze vytvořit:\n{e}")
            return
        self.cancelled = False
        self.bar["value"] = 0
        self._set_busy(True)
        self.worker = threading.Thread(
            target=self._download_worker,
            args=(urls, outdir, self.quality.get(), self.playlist.get(), self.thumb.get()),
            daemon=True,
        )
        self.worker.start()

    def _cancel(self):
        self.cancelled = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.q.put(("log", "Rušeno uživatelem."))

    def _update(self):
        self._set_busy(True)
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self):
        try:
            exe = self._ensure_ytdlp()
            self._run([exe, "-U"])
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", f"Chyba: {e}"))
        self.q.put(("done", None))

    def _download_worker(self, urls, outdir, quality, playlist, thumb):
        try:
            exe = self._ensure_ytdlp()
            self._ensure_ffmpeg()
            ok = 0
            for i, url in enumerate(urls, 1):
                if self.cancelled:
                    break
                self.q.put(("status", f"[{i}/{len(urls)}] {url}"))
                tmpl = (
                    "%(playlist_title)s/%(playlist_index)s - %(title)s.%(ext)s"
                    if playlist else "%(title)s.%(ext)s"
                )
                cmd = [
                    exe, "-x", "--audio-format", "mp3", "--audio-quality", f"{quality}K",
                    "-P", outdir, "-o", tmpl,
                    "--yes-playlist" if playlist else "--no-playlist",
                    "--newline", "--encoding", "utf-8", "--windows-filenames",
                    "--progress-template", f"download:{PROG_PREFIX}%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
                ]
                if thumb:
                    cmd += ["--embed-metadata", "--embed-thumbnail", "--convert-thumbnails", "jpg"]
                ff = os.path.join(APP_DIR, "ffmpeg.exe")
                if os.path.isfile(ff):
                    cmd += ["--ffmpeg-location", APP_DIR]
                cmd.append(url)
                if self._run(cmd) == 0:
                    ok += 1
            self.q.put(("status", f"Hotovo: {ok}/{len(urls)} úspěšně" if not self.cancelled else "Zrušeno"))
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", f"Chyba: {e}"))
            self.q.put(("status", "Chyba"))
        self.q.put(("done", None))

    def _run(self, cmd):
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
        )
        for line in self.proc.stdout:
            line = line.rstrip()
            if line:
                self.q.put(("line", line))
        self.proc.wait()
        return self.proc.returncode

    # ---------- Queue → UI ----------
    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "line":
                    if val.startswith(PROG_PREFIX):
                        self._on_progress(val[len(PROG_PREFIX):])
                    else:
                        self._log(val)
                        if "[ExtractAudio]" in val:
                            self.status.configure(text="Převádím do MP3…")
                elif kind == "log":
                    self._log(val)
                elif kind == "bar":
                    self.bar["value"] = val
                elif kind == "status":
                    self.status.configure(text=val)
                elif kind == "done":
                    self._set_busy(False)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _on_progress(self, s):
        try:
            pct, speed, eta = (p.strip() for p in s.split("|"))
            self.bar["value"] = float(pct.rstrip("%"))
            self.status.configure(text=f"{pct}  •  {speed}  •  ETA {eta}")
        except ValueError:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()

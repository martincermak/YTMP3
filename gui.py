"""GUI YT MP3 (CustomTkinter, pouze tmavý motiv) podle schváleného návrhu."""
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageDraw

import core

# ------------------------------------------------------------------ barvy
BG = "#0E0F12"
SURFACE = "#17181C"
SURFACE2 = "#1F2127"
TRACK = "#2A2D35"
LINE = "#26282E"
TEXT = "#F2F3F5"
MUTED = "#9AA0AB"
PLACEHOLDER = "#8A909B"
ACCENT = "#C8F25A"
ACCENT_HOVER = "#B4DD47"
INK = "#0E0F12"
ERR = "#FF8A7A"
ERR_BG = "#372829"
ERR_LINE = "#744542"
FONT = "Segoe UI"


def F(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


# ------------------------------------------------------------------ ikony
_SS = 8  # supersampling kvůli hladkým hranám
_BICUBIC = getattr(getattr(Image, "Resampling", Image), "BICUBIC")
_icon_cache = {}


def ic(name, color=TEXT, size=20, width=1.75):
    """Čárová ikona (24×24 viewBox jako v návrhu) jako CTkImage."""
    key = (name, color, size, width)
    if key in _icon_cache:
        return _icon_cache[key]
    n = size * _SS
    k = n / 24.0
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = max(1, int(round(width * k)))

    def line(p):
        q = [(x * k, y * k) for x, y in p]
        d.line(q, fill=color, width=w, joint="curve")
        r = w / 2.0
        for x, y in (q[0], q[-1]):
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    def circle(cx, cy, r, fill=False):
        box = [(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k]
        if fill:
            d.ellipse(box, fill=color)
        else:
            d.ellipse(box, outline=color, width=w)

    def rrect(x0, y0, x1, y1, r):
        d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], radius=r * k,
                            outline=color, width=w)

    if name == "sliders":
        line([(4, 7), (14, 7)])
        line([(18, 7), (20, 7)])
        circle(16, 7, 2)
        line([(4, 17), (6, 17)])
        line([(10, 17), (20, 17)])
        circle(8, 17, 2)
    elif name == "link":
        layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle([1.5 * k, 8.5 * k, 13.5 * k, 15.5 * k], radius=3.5 * k,
                             outline=color, width=w)
        ld.rounded_rectangle([10.5 * k, 8.5 * k, 22.5 * k, 15.5 * k], radius=3.5 * k,
                             outline=color, width=w)
        layer = layer.rotate(45, resample=_BICUBIC, center=(n / 2.0, n / 2.0))
        img.alpha_composite(layer)
    elif name == "paste":
        rrect(5, 5, 19, 21, 2)
        rrect(9, 3, 15, 7, 1)
    elif name == "download":
        line([(12, 4), (12, 15)])
        line([(7, 11), (12, 16), (17, 11)])
        line([(5, 20), (19, 20)])
    elif name == "folder":
        line([(3, 7), (3, 17), (5, 19), (19, 19), (21, 17), (21, 9), (19, 7),
              (11, 7), (9, 5), (5, 5), (3, 7)])
    elif name == "chevron_down":
        line([(6, 9), (12, 15), (18, 9)])
    elif name == "chevron_up":
        line([(6, 15), (12, 9), (18, 15)])
    elif name == "check":
        circle(12, 12, 9)
        line([(8, 12.5), (10.7, 15.2), (16, 9.5)])
    elif name == "x":
        line([(6, 6), (18, 18)])
        line([(18, 6), (6, 18)])
    elif name == "plus":
        line([(12, 5), (12, 19)])
        line([(5, 12), (19, 12)])
    elif name == "alert":
        line([(12, 4), (21, 20), (3, 20), (12, 4)])
        line([(12, 10), (12, 14)])
        circle(12, 17.5, 0.7, fill=True)
    elif name == "music":
        line([(9, 18), (9, 6), (19, 4), (19, 16)])
        circle(6.5, 18, 2.5)
        circle(16.5, 16, 2.5)
    elif name == "back":
        line([(19, 12), (5, 12)])
        line([(11, 6), (5, 12), (11, 18)])
    elif name == "refresh":
        box = [4 * k, 4 * k, 20 * k, 20 * k]
        d.arc(box, start=340, end=360, fill=color, width=w)
        d.arc(box, start=0, end=290, fill=color, width=w)
        line([(20, 4), (20, 9), (15, 9)])
    else:
        raise ValueError(f"neznámá ikona: {name}")

    out = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _icon_cache[key] = out
    return out


def make_logo(size=32):
    n = size * _SS
    k = n / 28.0
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=8 * k, fill=ACCENT)
    for x, h in ((6.2, 6), (10.6, 14), (15.0, 9), (19.4, 4)):
        d.rounded_rectangle([x * k, (14 - h / 2.0) * k, (x + 2.6) * k, (14 + h / 2.0) * k],
                            radius=1.3 * k, fill=INK)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


# ---------------------------------------------------------------- pomocné
def shorten(text, n=34):
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def display_url(url):
    return re.sub(r"^https?://(www\.)?", "", url or "")


def fmt_speed(s):
    m = re.match(r"^([\d.]+)\s*([KMG]?)i?B/s$", s or "", re.I)
    if not m:
        return ""
    return f"{float(m.group(1)):.1f}".replace(".", ",") + f" {m.group(2).upper()}B/s"


def fmt_eta(s):
    s = (s or "").strip()
    if not s or "unknown" in s.lower() or s == "NA":
        return ""
    return s[1:] if s.startswith("00:") else s


def fmt_size(n):
    return f"{n / 1e6:.1f}".replace(".", ",") + " MB"


def parse_prog(line):
    parts = line[len(core.PROG_PREFIX):].split("|", 4)
    while len(parts) < 5:
        parts.append("")
    pct_s, speed, eta, dur, title = [p.strip() for p in parts]
    try:
        pct = float(pct_s.rstrip("%"))
    except ValueError:
        pct = None
    dur = "" if dur in ("NA", "") else dur
    title = "" if title in ("NA", "") else title
    return pct, fmt_speed(speed), fmt_eta(eta), dur, title


def icon_button(parent, name, command, label=None, size=40):
    return ctk.CTkButton(parent, text="", image=ic(name, TEXT, 18), width=size, height=size,
                         corner_radius=12, fg_color=SURFACE2, hover_color=TRACK,
                         command=command)


# ------------------------------------------------------------- karta fronty
class Item(ctk.CTkFrame):
    def __init__(self, app, master, iid, url, opts):
        super().__init__(master, fg_color=SURFACE, corner_radius=18, border_width=1,
                         border_color=LINE)
        self.app = app
        self.iid = iid
        self.url = url
        self.opts = opts
        self.st = "queued"
        self.cancelled = False
        self.path = None
        self.full_title = None
        self.grid_columnconfigure(1, weight=1)

        self.thumb = ctk.CTkFrame(self, width=52, height=52, corner_radius=12, fg_color=SURFACE2)
        self.thumb.grid(row=0, column=0, padx=14, pady=14, sticky="n")
        self.thumb_icon = ctk.CTkLabel(self.thumb, text="", image=ic("music", MUTED, 22))
        self.thumb_icon.place(relx=0.5, rely=0.5, anchor="center")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=1, sticky="ew", pady=14)
        self.lbl_title = ctk.CTkLabel(self.body, text="", anchor="w", justify="left",
                                      font=F(14, "bold"), text_color=TEXT)
        self.bar = ctk.CTkProgressBar(self.body, height=6, corner_radius=3, fg_color=TRACK,
                                      progress_color=ACCENT)
        self.bar.set(0)
        self.meta = ctk.CTkLabel(self.body, text="", anchor="w", justify="left", font=F(12),
                                 text_color=MUTED, wraplength=270)
        self.err_row = ctk.CTkFrame(self.body, fg_color="transparent")
        ctk.CTkButton(self.err_row, text="Zkusit znovu", width=110, height=36, corner_radius=10,
                      fg_color=SURFACE2, hover_color=TRACK, text_color=TEXT,
                      font=F(13, "bold"), command=lambda: app.retry(iid)).pack(side="left")
        ctk.CTkButton(self.err_row, text="Podrobnosti", width=96, height=36, corner_radius=10,
                      fg_color="transparent", hover_color=SURFACE2, text_color=MUTED,
                      font=F(13, "bold"), command=app.show_log).pack(side="left", padx=(8, 0))

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.grid(row=0, column=2, padx=(0, 14), pady=14, sticky="n")
        self.done_icon = ctk.CTkLabel(self.actions, text="", image=ic("check", ACCENT, 24))
        self.btn_folder = icon_button(self.actions, "folder", lambda: app.reveal(self))
        self.btn_x = icon_button(self.actions, "x", lambda: app.cancel_item(iid))
        self.set_state("queued")

    def _clear(self):
        for w in (self.lbl_title, self.bar, self.meta, self.err_row,
                  self.done_icon, self.btn_folder, self.btn_x):
            w.pack_forget()

    def set_state(self, st, head=None, meta=None, title=None, path=None):
        self.st = st
        self._clear()
        err = st == "error"
        self.configure(border_color=ERR_LINE if err else LINE)
        self.thumb.configure(fg_color=ERR_BG if err else SURFACE2)
        self.thumb_icon.configure(image=ic("alert", ERR, 22) if err else ic("music", MUTED, 22))
        if title:
            self.full_title = title
        if path:
            self.path = path
        self.lbl_title.configure(text=shorten(head if err else (self.full_title or display_url(self.url))))
        self.lbl_title.pack(fill="x")

        if st == "queued":
            self.meta.configure(text="Čeká ve frontě")
            self.meta.pack(fill="x", pady=(3, 0))
            self.btn_x.pack(side="left")
        elif st == "downloading":
            self.bar.configure(mode="determinate")
            self.bar.pack(fill="x", pady=(10, 0))
            self.meta.configure(text=meta or "Zahajuji stahování…")
            self.meta.pack(fill="x", pady=(8, 0))
            self.btn_x.pack(side="left")
        elif st == "converting":
            self.bar.set(1)
            self.bar.pack(fill="x", pady=(10, 0))
            self.meta.configure(text="Převádím do MP3…")
            self.meta.pack(fill="x", pady=(8, 0))
            self.btn_x.pack(side="left")
        elif st == "done":
            self.meta.configure(text=meta or "")
            self.meta.pack(fill="x", pady=(3, 0))
            self.done_icon.pack(side="left", padx=(0, 8))
            self.btn_folder.pack(side="left")
        elif st == "error":
            self.meta.configure(text=meta or "")
            self.meta.pack(fill="x", pady=(3, 0))
            self.err_row.pack(anchor="w", pady=(10, 0))
            self.btn_x.pack(side="left")

    def set_progress(self, pct, speed, eta, title):
        if title and title != self.full_title:
            self.full_title = title
            self.lbl_title.configure(text=shorten(title))
        if pct is None:
            return
        self.bar.set(max(0.0, min(1.0, pct / 100.0)))
        parts = [f"{pct:.0f} %"]
        if speed:
            parts.append(speed)
        if eta:
            parts.append(f"zbývá {eta}")
        self.meta.configure(text=" · ".join(parts))


# ---------------------------------------------------------------- aplikace
class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=BG)
        self.title("YT MP3")
        self.geometry("520x720")
        self.minsize(460, 600)

        self.settings = core.load_settings()
        self.events = queue.Queue()
        self.jobs = queue.Queue()
        self.items = {}
        self.next_id = 1
        self.current = None
        self.deps_ready = False
        self.status_text = ""
        self.version = None
        self.quality_ctrls = []
        self.folder_btns = []

        self._build_main()
        self._build_settings()
        self._show("main")
        self._apply_log()
        self._layout()

        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._load_version, daemon=True).start()
        self.after(60, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------- stavba UI
    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=18, border_width=1,
                            border_color=LINE)

    def _row(self, card, title, sub, make_control, first=False):
        if not first:
            ctk.CTkFrame(card, height=1, fg_color=LINE).pack(fill="x")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=9)
        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text=title, font=F(14, "bold"), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        sub_lbl = None
        if sub:
            sub_lbl = ctk.CTkLabel(left, text=sub, font=F(12), text_color=MUTED, anchor="w",
                                   justify="left")
            sub_lbl.pack(anchor="w", pady=(2, 0))
        make_control(row).pack(side="right", padx=(12, 0))
        return sub_lbl

    def _quality_ctrl(self, parent):
        c = ctk.CTkSegmentedButton(
            parent, values=["128", "192", "256", "320"], command=self._set_quality,
            fg_color=BG, selected_color=TRACK, selected_hover_color=TRACK,
            unselected_color=BG, unselected_hover_color=SURFACE2, text_color=TEXT,
            corner_radius=12, border_width=4, height=44, font=F(13, "bold"))
        c.set(self.settings["quality"])
        self.quality_ctrls.append(c)
        return c

    def _folder_btn(self, parent):
        b = ctk.CTkButton(parent, text=self._folder_label(), image=ic("folder", TEXT, 16),
                          compound="left", fg_color=SURFACE2, hover_color=TRACK,
                          text_color=TEXT, corner_radius=12, height=44, font=F(13, "bold"),
                          command=self._pick_folder)
        self.folder_btns.append(b)
        return b

    def _switch(self, parent, key):
        var = tk.BooleanVar(value=bool(self.settings[key]))
        sw = ctk.CTkSwitch(parent, text="", variable=var, onvalue=True, offvalue=False,
                           width=46, switch_width=46, switch_height=26, fg_color=TRACK,
                           progress_color=ACCENT, button_color=TEXT, button_hover_color="#FFFFFF",
                           command=lambda: self._on_switch(key, var))
        if key == "details":
            self.details_var = var
        return sw

    def _make_input(self, parent, height, placeholder, make_right):
        box = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=height // 3, border_width=1,
                           border_color=LINE, height=height)
        box.pack_propagate(False)
        ctk.CTkLabel(box, text="", image=ic("link", MUTED, 20)).pack(side="left", padx=(18, 0))
        make_right(box).pack(side="right", padx=8)
        entry = ctk.CTkEntry(box, placeholder_text=placeholder, fg_color="transparent",
                             border_width=0, text_color=TEXT, placeholder_text_color=PLACEHOLDER,
                             font=F(15), height=height - 12)
        entry.pack(side="left", fill="x", expand=True, padx=(10, 6))
        entry.bind("<<Paste>>", lambda e: self._on_paste())
        entry.bind("<Return>", lambda e, en=entry: self._submit(en))
        return box, entry

    def _build_main(self):
        self.main = ctk.CTkFrame(self, fg_color="transparent")

        hdr = ctk.CTkFrame(self.main, fg_color="transparent", height=60)
        hdr.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(hdr, text="", image=make_logo(32)).pack(side="left")
        ctk.CTkButton(hdr, text="", image=ic("sliders", TEXT, 20), width=44, height=44,
                      corner_radius=14, fg_color="transparent", hover_color=SURFACE,
                      border_width=1, border_color=LINE,
                      command=lambda: self._show("settings")).pack(side="right")

        # patička + log (zespodu)
        self.footer = ctk.CTkFrame(self.main, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", pady=(10, 0))
        self.footer_left = ctk.CTkLabel(self.footer, text="", font=F(12), text_color=MUTED,
                                        anchor="w")
        self.footer_left.pack(side="left")
        self.btn_log = ctk.CTkButton(self.footer, text="Podrobnosti", compound="right",
                                     image=ic("chevron_up", MUTED, 14, 2), width=104, height=32,
                                     fg_color="transparent", hover_color=SURFACE,
                                     text_color=MUTED, font=F(12, "bold"),
                                     command=self._toggle_log)
        self.btn_log.pack(side="right")
        self.btn_cancel_all = ctk.CTkButton(self.footer, text="Zrušit vše", width=84, height=32,
                                            fg_color="transparent", hover_color=SURFACE,
                                            text_color=MUTED, font=F(12, "bold"),
                                            command=self.cancel_all)
        self.log = ctk.CTkTextbox(self.main, height=150, fg_color=SURFACE, text_color=MUTED,
                                  border_width=1, border_color=LINE, corner_radius=12,
                                  font=ctk.CTkFont(family="Consolas", size=11), wrap="word")
        self.log.configure(state="disabled")

        # --- prázdný stav
        self.empty = ctk.CTkFrame(self.main, fg_color="transparent")
        ctk.CTkLabel(self.empty, text="Z videa\nudělej MP3", font=F(36, "bold"), text_color=TEXT,
                     anchor="w", justify="left").pack(anchor="w", pady=(22, 0))
        ctk.CTkLabel(self.empty, text="Vlož odkaz z YouTube. Zbytek už se postará aplikace.",
                     font=F(15), text_color=MUTED, anchor="w", justify="left",
                     wraplength=440).pack(anchor="w", pady=(10, 0))

        def paste_btn(parent):
            return ctk.CTkButton(parent, text="Vložit", image=ic("paste", TEXT, 16),
                                 compound="left", width=88, height=40, corner_radius=12,
                                 fg_color=SURFACE2, hover_color=TRACK, text_color=TEXT,
                                 font=F(13, "bold"), command=self._paste_button)

        self.box_big, self.entry_big = self._make_input(
            self.empty, 60, "Vlož odkaz na video nebo playlist", paste_btn)
        self.box_big.pack(fill="x", pady=(28, 0))
        ctk.CTkButton(self.empty, text="Stáhnout MP3", image=ic("download", INK, 20, 2),
                      compound="left", height=56, corner_radius=16, fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, text_color=INK, font=F(16, "bold"),
                      command=lambda: self._submit(self.entry_big)).pack(fill="x", pady=(12, 0))
        card = self._card(self.empty)
        card.pack(fill="x", pady=(22, 0))
        self._row(card, "Kvalita", "kbps", self._quality_ctrl, first=True)
        self._row(card, "Uložit do", "Kam se uloží hotové MP3", self._folder_btn)
        ctk.CTkLabel(self.empty, text="Vlož víc odkazů najednou – každý se zařadí do fronty.",
                     font=F(13), text_color=PLACEHOLDER).pack(pady=(18, 0))

        # --- fronta
        self.queue_view = ctk.CTkFrame(self.main, fg_color="transparent")

        def add_btn(parent):
            return ctk.CTkButton(parent, text="", image=ic("plus", INK, 20, 2), width=40,
                                 height=40, corner_radius=12, fg_color=ACCENT,
                                 hover_color=ACCENT_HOVER,
                                 command=lambda: self._submit(self.entry_small))

        self.box_small, self.entry_small = self._make_input(
            self.queue_view, 56, "Přidat další odkaz…", add_btn)
        self.box_small.pack(fill="x", pady=(6, 0))
        head = ctk.CTkFrame(self.queue_view, fg_color="transparent")
        head.pack(fill="x", pady=(22, 0))
        ctk.CTkLabel(head, text="Fronta", font=F(15, "bold"), text_color=TEXT).pack(side="left")
        self.count_lbl = ctk.CTkLabel(head, text="", font=F(13), text_color=MUTED)
        self.count_lbl.pack(side="right")
        self.list_frame = ctk.CTkScrollableFrame(
            self.queue_view, fg_color="transparent", scrollbar_button_color=SURFACE,
            scrollbar_button_hover_color=TRACK)
        self.list_frame.pack(fill="both", expand=True, pady=(10, 0))

    def _build_settings(self):
        self.settings_view = ctk.CTkFrame(self, fg_color="transparent")
        hdr = ctk.CTkFrame(self.settings_view, fg_color="transparent", height=60)
        hdr.pack(fill="x", pady=(6, 0))
        ctk.CTkButton(hdr, text="", image=ic("back", TEXT, 20), width=44, height=44,
                      corner_radius=14, fg_color="transparent", hover_color=SURFACE,
                      border_width=1, border_color=LINE,
                      command=lambda: self._show("main")).pack(side="left")
        ctk.CTkLabel(hdr, text="Nastavení", font=F(22, "bold"), text_color=TEXT).pack(
            side="left", padx=(14, 0))

        ctk.CTkLabel(self.settings_view, text="Stahování", font=F(13, "bold"),
                     text_color=MUTED, anchor="w").pack(fill="x", padx=4, pady=(20, 8))
        card = self._card(self.settings_view)
        card.pack(fill="x")
        self._row(card, "Kvalita", "Vyšší číslo = větší soubor (kbps)", self._quality_ctrl,
                  first=True)
        self._row(card, "Uložit do", "Kam se uloží hotové MP3", self._folder_btn)
        self._row(card, "Celý playlist", "Stáhne všechna videa do podsložky",
                  lambda p: self._switch(p, "playlist"))
        self._row(card, "Obal alba a metadata", "Vloží náhled videa jako obal MP3",
                  lambda p: self._switch(p, "thumb"))

        ctk.CTkLabel(self.settings_view, text="Údržba", font=F(13, "bold"), text_color=MUTED,
                     anchor="w").pack(fill="x", padx=4, pady=(22, 8))
        card2 = self._card(self.settings_view)
        card2.pack(fill="x")

        def update_btn(parent):
            self.btn_update = ctk.CTkButton(
                parent, text="Aktualizovat", image=ic("refresh", TEXT, 16), compound="left",
                fg_color=SURFACE2, hover_color=TRACK, text_color=TEXT, corner_radius=12,
                height=44, font=F(13, "bold"), command=self._update_ytdlp)
            return self.btn_update

        self.ytdlp_sub = self._row(card2, "yt-dlp", "Nástroj, který stahuje z YouTube",
                                   update_btn, first=True)
        self._row(card2, "Podrobnosti stahování", "Technický výpis pro řešení problémů",
                  lambda p: self._switch(p, "details"))

        ctk.CTkLabel(self.settings_view, text="YT MP3 · verze 1.0.0", font=F(12),
                     text_color=MUTED).pack(side="bottom", pady=(14, 0))

    # --------------------------------------------------------- zobrazení
    def _show(self, name):
        self.main.pack_forget()
        self.settings_view.pack_forget()
        target = self.main if name == "main" else self.settings_view
        target.pack(fill="both", expand=True, padx=32, pady=(0, 22))

    def _layout(self):
        if self.items:
            self.empty.pack_forget()
            self.queue_view.pack(fill="both", expand=True)
            self.btn_cancel_all.pack(side="right", padx=(0, 4))
        else:
            self.queue_view.pack_forget()
            self.empty.pack(fill="both", expand=True)
            self.btn_cancel_all.pack_forget()
        done = sum(1 for i in self.items.values() if i.st == "done")
        self.count_lbl.configure(text=f"{done} z {len(self.items)} hotovo")
        self._refresh_footer()

    def _refresh_footer(self):
        if self.status_text:
            txt = self.status_text
        elif self.items:
            txt = f"Ukládá se do {self._folder_label()}"
        elif self.version:
            txt = f"yt-dlp {self.version}"
        else:
            txt = "yt-dlp se doplní při prvním stažení"
        self.footer_left.configure(text=txt)

    def _apply_log(self):
        if self.settings["details"]:
            self.log.pack(side="bottom", fill="x", after=self.footer, pady=(8, 0))
            self.btn_log.configure(image=ic("chevron_down", MUTED, 14, 2))
        else:
            self.log.pack_forget()
            self.btn_log.configure(image=ic("chevron_up", MUTED, 14, 2))
        if hasattr(self, "details_var"):
            self.details_var.set(bool(self.settings["details"]))

    def _toggle_log(self):
        self.settings["details"] = not self.settings["details"]
        core.save_settings(self.settings)
        self._apply_log()

    def show_log(self):
        self.settings["details"] = True
        core.save_settings(self.settings)
        self._apply_log()
        self._show("main")

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------- nastavení
    def _folder_label(self):
        base = os.path.basename(os.path.normpath(self.settings["outdir"])) or self.settings["outdir"]
        return "Hudba" if base.lower() == "music" else shorten(base, 18)

    def _set_quality(self, value):
        self.settings["quality"] = value
        for c in self.quality_ctrls:
            c.set(value)
        core.save_settings(self.settings)

    def _pick_folder(self):
        d = filedialog.askdirectory(initialdir=self.settings["outdir"])
        if d:
            self.settings["outdir"] = d
            for b in self.folder_btns:
                b.configure(text=self._folder_label())
            core.save_settings(self.settings)
            self._refresh_footer()

    def _on_switch(self, key, var):
        self.settings[key] = bool(var.get())
        core.save_settings(self.settings)
        if key == "details":
            self._apply_log()

    def _update_ytdlp(self):
        self.btn_update.configure(state="disabled", text="Aktualizuji…")
        self.status_text = "Aktualizuji yt-dlp…"
        self._refresh_footer()

        def work():
            try:
                v = core.update_ytdlp(self._report)
            except Exception as e:  # noqa: BLE001
                self.events.put(("log", f"Chyba aktualizace: {e}"))
                v = None
            self.events.put(("updated", v))

        threading.Thread(target=work, daemon=True).start()

    def _load_version(self):
        exe = core.find_tool("yt-dlp")
        self.events.put(("version", core.tool_version(exe) if exe else None))

    # --------------------------------------------------------- vstup URL
    def _report(self, kind, value):
        if kind in ("log", "status"):
            self.events.put((kind, value))

    def _on_paste(self):
        try:
            urls = core.parse_urls(self.clipboard_get())
        except tk.TclError:
            return None
        if len(urls) > 1:
            self._add_urls(urls)
            return "break"
        return None

    def _paste_button(self):
        try:
            urls = core.parse_urls(self.clipboard_get())
        except tk.TclError:
            return
        if len(urls) == 1:
            self.entry_big.delete(0, "end")
            self.entry_big.insert(0, urls[0])
        elif urls:
            self._add_urls(urls)

    def _submit(self, entry):
        urls = core.parse_urls(entry.get())
        if not urls:
            box = entry.master
            box.configure(border_color=ERR)
            self.after(900, lambda: box.configure(border_color=LINE))
            return
        entry.delete(0, "end")
        self._add_urls(urls)

    def _add_urls(self, urls):
        opts = {k: self.settings[k] for k in ("outdir", "quality", "playlist", "thumb")}
        for url in urls:
            iid = self.next_id
            self.next_id += 1
            item = Item(self, self.list_frame, iid, url, dict(opts))
            item.pack(fill="x", pady=(0, 10))
            self.items[iid] = item
            self.jobs.put(iid)
        self._layout()

    # ------------------------------------------------------ akce nad frontou
    def _remove_item(self, iid):
        item = self.items.pop(iid, None)
        if item:
            item.destroy()
        self._layout()

    def cancel_item(self, iid):
        item = self.items.get(iid)
        if not item:
            return
        item.cancelled = True
        cur = self.current
        if cur and cur[0] is item:
            try:
                cur[1].terminate()
            except OSError:
                pass
        self._remove_item(iid)

    def cancel_all(self):
        for iid in list(self.items):
            if self.items[iid].st != "done":
                self.cancel_item(iid)

    def retry(self, iid):
        item = self.items.get(iid)
        if item:
            item.cancelled = False
            item.set_state("queued")
            self.jobs.put(iid)

    def reveal(self, item):
        try:
            if sys.platform.startswith("win"):
                if item.path and os.path.exists(item.path):
                    subprocess.Popen(f'explorer /select,"{os.path.normpath(item.path)}"')
                else:
                    os.startfile(item.opts["outdir"])  # noqa: S606
        except OSError:
            pass

    # ------------------------------------------------------- pracovní vlákno
    def _worker(self):
        while True:
            iid = self.jobs.get()
            item = self.items.get(iid)
            if item is None or item.cancelled:
                continue
            try:
                self._run_item(item)
            except Exception as e:  # noqa: BLE001
                self.events.put(("log", f"[{iid}] neočekávaná chyba: {e}"))
                self.events.put(("state", iid, "error",
                                 {"head": core.DEFAULT_ERROR_TITLE, "meta": str(e)[:160]}))

    def _run_item(self, item):
        iid = item.iid
        if not self.deps_ready:
            self.events.put(("state", iid, "downloading", {"meta": "Připravuji nástroje…"}))
            try:
                core.ensure_all(self._report)
                self.deps_ready = True
            except Exception as e:  # noqa: BLE001
                head, msg = core.friendly_error(str(e))
                if head == core.DEFAULT_ERROR_TITLE:
                    head, msg = "Nepodařilo se připravit nástroje", str(e)[:160]
                self.events.put(("log", f"[{iid}] {e}"))
                self.events.put(("status", ""))
                self.events.put(("state", iid, "error", {"head": head, "meta": msg}))
                return
            self.events.put(("status", ""))
            if item.cancelled:
                return

        o = item.opts
        cmd = core.build_command(core.find_tool("yt-dlp"), item.url, o["outdir"], o["quality"],
                                 o["playlist"], o["thumb"])
        self.events.put(("state", iid, "downloading", {}))
        lines, final, dur, got_title = [], None, "", False
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", creationflags=core.NO_WINDOW)
        self.current = (item, proc)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if line.startswith(core.PROG_PREFIX):
                pct, speed, eta, d, title = parse_prog(line)
                dur = d or dur
                got_title = got_title or bool(title)
                self.events.put(("progress", iid, pct, speed, eta, title))
                continue
            lines.append(line)
            self.events.put(("log", f"[{iid}] {line}"))
            m = re.match(r"^\[ExtractAudio\] Destination: (.+)$", line)
            if m:
                final = m.group(1).strip()
            m = re.match(r"^\[download\] (.+) has already been downloaded$", line)
            if m and m.group(1).lower().endswith(".mp3"):
                final = m.group(1).strip()
            if line.startswith("[ExtractAudio]"):
                self.events.put(("state", iid, "converting", {}))
        proc.wait()
        self.current = None
        if item.cancelled:
            return
        if proc.returncode == 0:
            parts = [dur] if dur else []
            parts.append(f"{o['quality']} kbps")
            if final and os.path.isfile(final):
                parts.append(fmt_size(os.path.getsize(final)))
            kw = {"meta": " · ".join(parts), "path": final}
            if final and not got_title:
                kw["title"] = os.path.splitext(os.path.basename(final))[0]
            self.events.put(("state", iid, "done", kw))
        else:
            head, msg = core.friendly_error("\n".join(lines))
            self.events.put(("state", iid, "error", {"head": head, "meta": msg}))

    # --------------------------------------------------- události do UI vlákna
    def _poll(self):
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(60, self._poll)

    def _handle(self, ev):
        kind = ev[0]
        if kind == "state":
            _, iid, st, kw = ev
            item = self.items.get(iid)
            if item and not item.cancelled:
                item.set_state(st, **kw)
                self._layout()
        elif kind == "progress":
            _, iid, pct, speed, eta, title = ev
            item = self.items.get(iid)
            if item and item.st == "downloading":
                item.set_progress(pct, speed, eta, title)
        elif kind == "log":
            self._append_log(ev[1])
        elif kind == "status":
            self.status_text = ev[1]
            self._refresh_footer()
        elif kind == "version":
            self.version = ev[1]
            self._refresh_footer()
            if self.version and self.ytdlp_sub:
                self.ytdlp_sub.configure(text=f"Verze {self.version}")
        elif kind == "updated":
            self.btn_update.configure(state="normal", text="Aktualizovat")
            self.status_text = ""
            if ev[1]:
                self.version = ev[1]
                self.ytdlp_sub.configure(text=f"Verze {ev[1]}")
            self._refresh_footer()

    def _on_close(self):
        core.save_settings(self.settings)
        cur = self.current
        if cur:
            try:
                cur[1].terminate()
            except OSError:
                pass
        self.destroy()


def run_gui():
    App().mainloop()

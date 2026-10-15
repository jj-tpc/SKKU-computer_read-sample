"""화면(GUI). tkinter만 쓰므로 Windows와 macOS에서 같은 코드로 동작한다."""
from __future__ import annotations

import json
import os
import queue
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk

from .link import LinkError, PowerPointLink, PptState, resolve_local_path
from .slides import SOURCES, Deck, load_deck, to_speech
from .tts import AudioOutput, Speaker, TTSUnavailable

APP_TITLE = "PPT 읽어주기"
DEFAULT_OUTPUT_LABEL = "시스템 기본 장치"
SETTINGS_FILE = Path.home() / ".ppt_reader_settings.json"
READING_BG = "#ffe08a"  # 지금 읽는 슬라이드 표시 색
EMPTY_SLIDE_PAUSE_MS = 1500  # 읽을 글이 없는 장에서 자동 발표가 쉬는 시간


class PrimaryButton(tk.Label):
    """파란 바탕에 흰 글씨인 주 버튼(예: [적용]).

    ttk 버튼과 macOS의 tk.Button은 운영체제 모양을 따르느라 배경색을 바꿀 수 없어서 Label로 만든다.
    """
    COLORS = {"normal": "#1a73e8", "hover": "#1765cc", "pressed": "#1557b0"}

    def __init__(self, master, text: str, command):
        super().__init__(master, text=text, bg=self.COLORS["normal"], fg="white",
                         padx=22, pady=4, cursor="hand2")
        self._command = command
        self.bind("<Enter>", lambda e: self.configure(bg=self.COLORS["hover"]))
        self.bind("<Leave>", lambda e: self.configure(bg=self.COLORS["normal"]))
        self.bind("<ButtonPress-1>", lambda e: self.configure(bg=self.COLORS["pressed"]))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_release(self, event):
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self.configure(bg=self.COLORS["hover" if inside else "normal"])
        if inside:  # 누른 채로 버튼 밖에서 떼면 취소한 것으로 본다
            self._command()


class App:
    def __init__(self, root: tk.Tk, initial_path: str | None = None):
        self.root = root
        self.events: queue.Queue = queue.Queue()  # 다른 스레드 -> 화면 스레드
        self.deck: Deck | None = None
        self.deck_mtime = 0.0
        self.current = -1  # 화면에 보이는 슬라이드 위치 (0부터)
        self.edits: dict[int, str] = {}  # 슬라이드 번호 -> 사용자가 고친 대본
        self.token = 0  # 읽기를 시작하거나 멈출 때마다 1씩 늘어난다
        self.reading: tuple[int, int] | None = None  # (token, 읽는 슬라이드 위치)
        self.speaker: Speaker | None = None
        self.link: PowerPointLink | None = None
        self.ppt_state: PptState | None = None
        self.voice_ids: dict[str, str] = {}
        self.output_choices: dict[str, AudioOutput | None] = {}  # 목록 글자 -> 장치 (None = 시스템 기본)
        self._fonts: dict[str, font.Font] = {}

        settings = _load_settings()
        saved_output = settings.get("output")
        self.output: AudioOutput | None = None  # None = 운영체제의 기본 출력 장치
        if isinstance(saved_output, dict) and saved_output.get("id"):
            self.output = AudioOutput(saved_output["id"], saved_output.get("name") or saved_output["id"])
        source = settings.get("source", "notes_first")
        self.source = source if source in [k for k, _ in SOURCES] else "notes_first"
        self.voice_var = tk.StringVar()
        self.speed_var = tk.DoubleVar(value=float(settings.get("speed", 1.0)))
        self.auto_next_var = tk.BooleanVar(value=settings.get("auto_next", False))
        self.read_on_change_var = tk.BooleanVar(value=settings.get("read_on_change", True))
        self.follow_var = tk.BooleanVar(value=False)
        self.topmost_var = tk.BooleanVar(value=settings.get("topmost", False))
        # 설정 화면에서 고르는 중인 값. [적용]을 눌러야 위의 값으로 옮겨진다.
        self.pending_voice = tk.StringVar()
        self.pending_output = tk.StringVar()
        self.pending_auto_next = tk.BooleanVar()
        self.pending_read_on_change = tk.BooleanVar()
        self.settings_open = False

        self._build_ui()
        self._init_speaker(settings.get("voice"))
        self.root.after(50, self._pump)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        if self.topmost_var.get():
            self.toggle_topmost()
        self._show_slide()
        if initial_path:
            self.open_file(initial_path)

    # ------------------------------------------------------------ 화면 구성

    def _build_ui(self):
        r = self.root
        r.title(APP_TITLE)

        # 맨 아래 상태 표시줄을 먼저 붙여야 창이 작아져도 가려지지 않는다. 두 화면이 함께 쓴다.
        self.status = ttk.Label(r, text="", padding=(10, 6), foreground="#333")
        self.status.pack(fill="x", side="bottom")
        self.status.bind("<Configure>", lambda e: self.status.configure(wraplength=e.width - 24))

        # [설정]을 누르면 main_view를 숨기고 같은 자리에 settings_view를 띄운다.
        self.main_view = ttk.Frame(r)
        self.main_view.pack(fill="both", expand=True)
        self.settings_view = self._build_settings(r)
        m = self.main_view

        top = ttk.Frame(m, padding=(10, 8))
        top.pack(fill="x")
        ttk.Button(top, text="파일 열기...", command=self.ask_open).pack(side="left")
        ttk.Checkbutton(top, text="PowerPoint 연동", variable=self.follow_var,
                        command=self.toggle_link).pack(side="left", padx=(14, 6))
        self.link_label = ttk.Label(top, text="", foreground="#555")
        self.link_label.pack(side="left")
        ttk.Button(top, text="⚙ 설정", command=self.open_settings).pack(side="right")
        ttk.Checkbutton(top, text="항상 위", variable=self.topmost_var,
                        command=self.toggle_topmost).pack(side="right", padx=(0, 12))

        ctrl = ttk.Frame(m, padding=(10, 8, 10, 0))
        ctrl.pack(fill="x", side="bottom")
        ttk.Button(ctrl, text="◀ 이전", command=self.prev_slide).pack(side="left")
        self.play_btn = ttk.Button(ctrl, text="▶ 읽기", width=10, command=self.read_current)
        self.play_btn.pack(side="left", padx=4)
        ttk.Button(ctrl, text="■ 정지", command=self.stop).pack(side="left")
        ttk.Button(ctrl, text="다음 ▶", command=self.next_slide).pack(side="left", padx=4)
        speed = ttk.Frame(ctrl)
        speed.pack(side="right")
        ttk.Label(speed, text="속도").pack(side="left")
        ttk.Scale(speed, from_=0.5, to=2.0, variable=self.speed_var, length=140,
                  command=lambda _v: self._update_speed_label()).pack(side="left", padx=6)
        self.speed_label = ttk.Label(speed, width=5)
        self.speed_label.pack(side="left")
        self._update_speed_label()

        panes = ttk.PanedWindow(m, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10)

        left = ttk.Frame(panes)
        # 창 크기는 픽셀이 아니라 글자 수로 정해서 화면 배율(DPI)이 달라도 잘리지 않게 한다.
        self.listbox = tk.Listbox(left, activestyle="none", exportselection=False, width=34,
                                  height=16, font=self._font("list", 11, 13))
        sb = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)
        panes.add(left, weight=1)

        right = ttk.Frame(panes, padding=(10, 0, 0, 0))
        self.header = ttk.Label(right, text="", font=self._font("header", 14, 17, "bold"))
        self.header.pack(fill="x")
        ttk.Label(right, text="읽을 대본 (여기서 고치면 고친 대로 읽습니다)",
                  foreground="#666").pack(fill="x", pady=(2, 4))
        edit_row = ttk.Frame(right)
        edit_row.pack(fill="x", side="bottom", pady=(4, 0))
        self.edited_label = ttk.Label(edit_row, text="", foreground="#b05000")
        self.edited_label.pack(side="left")
        ttk.Button(edit_row, text="원래 내용으로", command=self.reset_edit).pack(side="right")
        box = ttk.Frame(right)
        box.pack(fill="both", expand=True)
        self.text = tk.Text(box, wrap="word", undo=True, font=self._font("text", 13, 15),
                            width=52, height=12, padx=10, pady=8)
        tsb = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=tsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        tsb.pack(side="left", fill="y")
        panes.add(right, weight=3)

        # 위젯들이 원하는 크기로 창 크기를 한 번 정해 두면, 긴 안내 문구가 떠도 창이 늘어나지 않는다.
        # 설정 화면도 같은 창에 들어가야 하므로 두 화면 중 큰 쪽에 맞춘다.
        r.update_idletasks()
        status_h = self.status.winfo_reqheight()
        w = max(r.winfo_reqwidth(), self.settings_view.winfo_reqwidth())
        h = max(r.winfo_reqheight(), self.settings_view.winfo_reqheight() + status_h) + status_h
        r.geometry(f"{w}x{h}")
        r.minsize(int(w * 0.75), int(h * 0.75))
        self.status.configure(wraplength=w - 24)

        r.bind("<space>", self._on_space)
        r.bind("<Escape>", lambda e: self.cancel_settings() if self.settings_open else self.stop())
        r.bind("<Return>", lambda e: self.apply_settings() if self.settings_open else None)
        r.bind("<F5>", lambda e: None if self.settings_open else self.read_current())
        r.bind("<Prior>", lambda e: self._unless_typing(e, self.prev_slide))
        r.bind("<Next>", lambda e: self._unless_typing(e, self.next_slide))

    def _build_settings(self, parent) -> ttk.Frame:
        sv = ttk.Frame(parent, padding=(20, 14, 20, 8))
        ttk.Label(sv, text="설정", font=self._font("header", 14, 17, "bold")).pack(anchor="w")
        ttk.Separator(sv).pack(fill="x", pady=(8, 14))

        # 맨 아래 [취소] [적용]을 먼저 붙여야 창이 작아져도 가려지지 않는다.
        buttons = ttk.Frame(sv)
        buttons.pack(side="bottom", fill="x", pady=(10, 0))
        PrimaryButton(buttons, text="적용", command=self.apply_settings).pack(side="right")
        ttk.Button(buttons, text="취소", command=self.cancel_settings).pack(side="right", padx=(0, 8))
        ttk.Separator(sv).pack(side="bottom", fill="x")

        form = ttk.Frame(sv)
        form.pack(fill="x")
        ttk.Label(form, text="읽을 내용").grid(row=0, column=0, sticky="w", pady=6)
        self.source_box = ttk.Combobox(form, state="readonly", width=22,
                                       values=[label for _, label in SOURCES])
        self.source_box.grid(row=0, column=1, sticky="w", padx=(12, 0), pady=6)
        ttk.Label(form, text="목소리").grid(row=1, column=0, sticky="w", pady=6)
        self.voice_box = ttk.Combobox(form, state="readonly", width=40, textvariable=self.pending_voice)
        self.voice_box.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=6)
        ttk.Label(form, text="출력 장치").grid(row=2, column=0, sticky="w", pady=(6, 0))
        # 목록을 펼 때마다 장치를 다시 읽어서, 나중에 연결한 블루투스 이어폰도 고를 수 있게 한다.
        self.output_box = ttk.Combobox(form, state="readonly", width=48, textvariable=self.pending_output,
                                       postcommand=lambda: self._refresh_outputs(self._pending_output()))
        self.output_box.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(form, text="목록을 펼 때마다 연결된 장치를 다시 찾습니다.",
                  foreground="#666").grid(row=3, column=1, sticky="w", padx=(12, 0), pady=(2, 6))

        ttk.Checkbutton(sv, text="다 읽으면 다음 장으로 넘어가기 (자동 발표)",
                        variable=self.pending_auto_next).pack(anchor="w", pady=(12, 4))
        ttk.Checkbutton(sv, text="슬라이드 쇼에서 장을 넘기면 바로 읽기",
                        variable=self.pending_read_on_change).pack(anchor="w", pady=4)
        return sv

    def _font(self, key: str, win_size: int, mac_size: int, weight: str = "normal") -> font.Font:
        if key not in self._fonts:
            size = win_size if sys.platform == "win32" else mac_size
            self._fonts[key] = font.Font(family=_ui_family(), size=size, weight=weight)
        return self._fonts[key]

    def _update_speed_label(self):
        self.speed_label.configure(text=f"{self.speed_var.get():.1f}배")

    def set_status(self, text: str):
        self.status.configure(text=text)

    # ------------------------------------------------------------ 음성

    def _init_speaker(self, saved_voice: str | None):
        try:
            self.speaker = Speaker(lambda kind, tag, info: self.events.put(("tts", kind, tag, info)))
        except TTSUnavailable as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        voices = self.speaker.voices()
        voices.sort(key=lambda v: not v.is_korean)  # 한국어 음성을 맨 앞에
        self.voice_ids = {(f"{v.name}  [{v.lang}]" if v.lang else v.name): v.id for v in voices}
        labels = list(self.voice_ids)
        self.voice_box.configure(values=labels)
        if saved_voice in labels:
            self.voice_var.set(saved_voice)
        elif labels:
            self.voice_var.set(labels[0])
        if not any(v.is_korean for v in voices):
            self.set_status("한국어 음성이 설치되어 있지 않습니다. README의 '한국어 음성 설치'를 참고하세요.")

    def _refresh_outputs(self, chosen: AudioOutput | None):
        """출력 장치 목록을 다시 읽고 chosen(None = 시스템 기본 장치)을 고른 상태로 둔다."""
        if self.speaker is None:
            return
        default = self.speaker.default_output()
        first = DEFAULT_OUTPUT_LABEL + (f" (지금: {default.name})" if default else "")
        self.output_choices = {first: None}
        for o in self.speaker.outputs():
            label, n = o.name, 2
            while label in self.output_choices:  # 이름이 같은 장치가 여러 개면 번호를 붙인다
                label, n = f"{o.name} ({n})", n + 1
            self.output_choices[label] = o
        selected = first
        if chosen is not None:
            selected = next((label for label, o in self.output_choices.items()
                             if o is not None and o.id == chosen.id), None)
            if selected is None:  # 고른 이어폰이 지금 연결되어 있지 않음: 연결되면 다시 그 장치로 읽는다
                selected = f"{chosen.name} (연결 안 됨 - 기본 장치로 읽음)"
                self.output_choices[selected] = chosen
        self.output_box.configure(values=list(self.output_choices))
        self.pending_output.set(selected)

    def _pending_output(self) -> AudioOutput | None:
        label = self.pending_output.get()
        return self.output_choices[label] if label in self.output_choices else self.output

    # ------------------------------------------------------------ 설정 화면

    def open_settings(self):
        if self.settings_open:
            return
        self._commit_edit()
        self.source_box.current([k for k, _ in SOURCES].index(self.source))
        self.pending_voice.set(self.voice_var.get())
        self._refresh_outputs(self.output)
        self.pending_auto_next.set(self.auto_next_var.get())
        self.pending_read_on_change.set(self.read_on_change_var.get())
        self.main_view.pack_forget()
        self.settings_view.pack(fill="both", expand=True)
        self.settings_open = True
        self.source_box.focus_set()

    def apply_settings(self):
        if not self.settings_open:
            return
        source = SOURCES[max(self.source_box.current(), 0)][0]
        source_changed = source != self.source
        self.source = source
        self.voice_var.set(self.pending_voice.get())
        self.output = self._pending_output()
        self.auto_next_var.set(self.pending_auto_next.get())
        self.read_on_change_var.set(self.pending_read_on_change.get())
        self._close_settings()
        if source_changed:
            self._show_slide()
        where = self.output.name if self.output else DEFAULT_OUTPUT_LABEL
        self.set_status(f"설정을 적용했습니다. 소리는 '{where}'(으)로 나옵니다.")

    def cancel_settings(self):
        if self.settings_open:
            self._close_settings()

    def _close_settings(self):
        self.settings_view.pack_forget()
        self.main_view.pack(fill="both", expand=True)
        self.settings_open = False

    def speak_slide(self, i: int):
        if self.speaker is None or self.deck is None:
            return
        self._commit_edit()
        slide = self.deck.slides[i]
        text = to_speech(self._script_for(i))
        self.token += 1
        self.reading = (self.token, i)
        self._mark_reading(i)
        if not text:
            self.speaker.stop()
            self.set_status(f"{slide.number}번 슬라이드에는 읽을 내용이 없습니다.")
            tok = self.token
            self.root.after(EMPTY_SLIDE_PAUSE_MS, lambda: self._on_read_finished(tok, True, quiet=True))
            return
        self.speaker.speak(text, self.voice_ids.get(self.voice_var.get()), self.speed_var.get(),
                           tag=self.token, output_id=self.output.id if self.output else None)
        self.set_status(f"{slide.number}번 슬라이드를 읽는 중...  (정지: Esc)")

    def read_current(self):
        if self.reading is not None:
            return
        if self.deck is None:
            self.set_status("먼저 [파일 열기]로 PPT 파일을 불러오거나 [PowerPoint 연동]을 켜세요.")
            return
        self.speak_slide(self.current)

    def stop(self, message: str = "정지했습니다."):
        was_reading = self.reading is not None
        self.token += 1
        self.reading = None
        self._mark_reading(None)
        if self.speaker:
            self.speaker.stop()
        if was_reading and message:
            self.set_status(message)

    def _on_read_finished(self, tok: int, completed: bool, quiet: bool = False):
        if self.reading is None or self.reading[0] != tok:
            return  # 그 사이 다른 슬라이드를 읽기 시작했거나 정지함
        i = self.reading[1]
        self.reading = None
        self._mark_reading(None)
        if not completed:
            return
        if not self.auto_next_var.get():
            if not quiet:
                self.set_status(f"{self.deck.slides[i].number}번 슬라이드를 다 읽었습니다.")
            return
        nxt = self._next_index(i)
        if nxt is None:
            self.set_status("마지막 슬라이드까지 모두 읽었습니다.")
            return
        self.select(nxt, sync_ppt=True)
        self.speak_slide(nxt)

    def _mark_reading(self, i: int | None):
        lb = self.listbox
        if not hasattr(self, "_select_colors"):
            self._select_colors = (lb.cget("selectbackground"), lb.cget("selectforeground"))
        for j in range(lb.size()):
            lb.itemconfigure(j, background="")
        if i is not None and 0 <= i < lb.size():
            lb.itemconfigure(i, background=READING_BG)
        # 읽는 장은 보통 선택된 장이기도 하므로 선택 색도 같은 색으로 바꿔 보이게 한다.
        reading_selected = i is not None and i == self.current
        lb.configure(selectbackground=READING_BG if reading_selected else self._select_colors[0],
                     selectforeground="black" if reading_selected else self._select_colors[1])
        self.play_btn.configure(text="● 읽는 중" if i is not None else "▶ 읽기")

    def _on_space(self, event):
        # 설정 화면이거나, 글자 입력 칸이나 버튼에 포커스가 있으면 그 위젯의 원래 동작을 따른다.
        if self.settings_open or isinstance(event.widget, (tk.Text, tk.Entry, ttk.Entry, tk.Button, ttk.Button,
                                     ttk.Checkbutton, tk.Checkbutton)):
            return
        if self.reading is not None:
            self.stop()
        else:
            self.read_current()
        return "break"

    def _unless_typing(self, event, action):
        if not self.settings_open and not isinstance(event.widget, tk.Text):
            action()
            return "break"

    # ------------------------------------------------------------ 파일 / 슬라이드

    def ask_open(self):
        path = filedialog.askopenfilename(
            title="발표할 PPT 파일 선택",
            filetypes=[("PowerPoint 프레젠테이션", "*.pptx *.pptm"), ("모든 파일", "*.*")])
        if path:
            self.open_file(path)

    def open_file(self, path: str | Path, keep_position: bool = False) -> bool:
        path = Path(path)
        if path.suffix.lower() in (".ppt", ".pps", ".key"):
            messagebox.showwarning(APP_TITLE, f"'{path.name}' 형식은 읽을 수 없습니다.\n"
                                   "PowerPoint에서 [다른 이름으로 저장] → .pptx 로 저장한 뒤 여세요.")
            return False
        try:
            deck = load_deck(path)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"파일을 열 수 없습니다.\n{path}\n\n{e}")
            return False
        self._commit_edit()
        self.stop(message="")
        if self.deck is None or not _same_path(self.deck.path, path):
            self.edits.clear()
        position = self.current if keep_position else 0
        self.deck = deck
        self.deck_mtime = _mtime(path)
        self.listbox.delete(0, "end")
        for s in deck.slides:
            label = (s.title or s.body).split("\n")[0] or "(내용 없음)"
            mark = "  (숨김)" if s.hidden else ""
            self.listbox.insert("end", f" {s.number:>2}. {label[:30]}{mark}")
        self.root.title(f"{deck.name} - {APP_TITLE}")
        self.current = -1
        self.select(min(max(position, 0), len(deck.slides) - 1))
        n_notes = sum(1 for s in deck.slides if s.notes)
        self.set_status(f"'{deck.name}' 불러옴: 슬라이드 {len(deck.slides)}장 "
                        f"(발표자 노트 있는 장 {n_notes}개). [▶ 읽기] 또는 스페이스바를 누르세요.")
        return True

    def select(self, i: int, user: bool = False, sync_ppt: bool = False):
        """i번째(0부터) 슬라이드를 화면에 띄운다.

        user=True: 사용자가 직접 고름 -> 읽던 것을 멈추고 PowerPoint 쇼도 같은 장으로 넘긴다.
        sync_ppt=True: PowerPoint 쇼만 같은 장으로 넘긴다(자동 발표).
        """
        if self.deck is None or not (0 <= i < len(self.deck.slides)):
            self._show_slide()
            return
        if i != self.current:
            self._commit_edit()
        self.current = i
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(i)
        self.listbox.activate(i)
        self.listbox.see(i)
        self._show_slide()
        if user:
            self.stop()
        if (user or sync_ppt) and self.link and self.ppt_state and self.ppt_state.mode == "show":
            self.link.goto_slide(self.deck.slides[i].number)

    def _on_list_select(self, _event):
        sel = self.listbox.curselection()
        if sel and sel[0] != self.current:
            self.select(sel[0], user=True)

    def prev_slide(self):
        if self.deck and self.current > 0:
            self.select(self.current - 1, user=True)

    def next_slide(self):
        if self.deck and self.current < len(self.deck.slides) - 1:
            self.select(self.current + 1, user=True)

    def _next_index(self, i: int) -> int | None:
        for j in range(i + 1, len(self.deck.slides)):
            if not self.deck.slides[j].hidden:  # 숨긴 슬라이드는 슬라이드 쇼처럼 건너뛴다
                return j
        return None

    def _script_for(self, i: int) -> str:
        slide = self.deck.slides[i]
        if slide.number in self.edits:
            return self.edits[slide.number]
        return slide.script(self.source)

    def _show_slide(self):
        self.text.delete("1.0", "end")
        if self.deck is None or not (0 <= self.current < len(self.deck.slides)):
            self.header.configure(text="PPT 파일을 열어 주세요")
            self.edited_label.configure(text="")
            self.set_status("[파일 열기]로 발표 자료(.pptx)를 불러오거나, PowerPoint에 띄워 두고 "
                            "[PowerPoint 연동]을 켜세요.")
        else:
            slide = self.deck.slides[self.current]
            title = slide.title.split("\n")[0]
            self.header.configure(text=f"슬라이드 {slide.number} / {len(self.deck.slides)}"
                                       + (f"  ·  {title}" if title else ""))
            self.text.insert("1.0", self._script_for(self.current))
            self.edited_label.configure(text="✎ 고친 대본" if slide.number in self.edits else "")
        self.text.edit_modified(False)
        self.text.edit_reset()

    def _commit_edit(self):
        """대본 칸에서 고친 내용을 기억해 둔다."""
        if self.deck is None or not (0 <= self.current < len(self.deck.slides)):
            return
        if not self.text.edit_modified():
            return
        slide = self.deck.slides[self.current]
        new = self.text.get("1.0", "end-1c")
        if new.strip() == slide.script(self.source).strip():
            self.edits.pop(slide.number, None)
        else:
            self.edits[slide.number] = new
        self.text.edit_modified(False)
        self.edited_label.configure(text="✎ 고친 대본" if slide.number in self.edits else "")

    def reset_edit(self):
        if self.deck is None or self.current < 0:
            return
        self.edits.pop(self.deck.slides[self.current].number, None)
        self._show_slide()

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())

    # ------------------------------------------------------------ PowerPoint 연동

    def toggle_link(self):
        if self.follow_var.get():
            try:
                self.link = PowerPointLink(
                    on_change=lambda st: self.events.put(("ppt", st)),
                    on_error=lambda msg: self.events.put(("ppt_error", msg)))
            except LinkError as e:
                self.follow_var.set(False)
                messagebox.showerror(APP_TITLE, str(e))
                return
            self.ppt_state = None
            self.link_label.configure(text="PowerPoint 찾는 중...")
        else:
            if self.link:
                self.link.close()
            self.link = None
            self.ppt_state = None
            self.link_label.configure(text="")

    def _on_ppt_state(self, st: PptState):
        prev = self.ppt_state
        self.ppt_state = st
        first = prev is None  # 연동을 막 켰을 때는 화면만 맞추고 읽지는 않는다
        if st.mode == "none":
            self.link_label.configure(text="PowerPoint에 열린 발표 자료가 없습니다")
            return
        where = "슬라이드 쇼" if st.mode == "show" else "편집 화면"
        self.link_label.configure(text=f"{where} · {st.index or '-'}번 · {_basename(st.path)}")
        if prev and prev.mode == "show" and st.mode != "show":
            self.stop(message="슬라이드 쇼가 끝나서 읽기를 멈췄습니다.")

        loaded = self._follow_file(st.path)
        if loaded is None or st.index is None or self.deck is None:
            return
        i = st.index - 1
        entered_show = st.mode == "show" and (prev is None or prev.mode != "show")
        if i == self.current and not loaded and not entered_show:
            return  # 이 프로그램이 넘긴 장이라 이미 맞춰져 있음
        self.select(i)
        if st.mode != "show" or first or loaded:
            return
        if self.read_on_change_var.get():
            self.speak_slide(i)
        elif self.reading is not None and self.reading[1] != i:
            self.stop()

    def _follow_file(self, ppt_path: str) -> bool | None:
        """PowerPoint에 열린 파일을 불러온다. 새로 불러왔으면 True, 이미 열려 있으면 False, 못 하면 None."""
        local = resolve_local_path(ppt_path)
        if local is None:
            if self.deck is not None and self.deck.name.lower() == _basename(ppt_path).lower():
                return False  # 경로는 모르지만 같은 이름의 파일을 이미 열어 두었음
            self.set_status(f"PowerPoint의 '{_basename(ppt_path)}' 파일 위치를 알 수 없습니다. "
                            "파일을 저장했는지 확인하거나 [파일 열기]로 같은 파일을 직접 여세요.")
            return None
        if self.deck is not None and _same_path(self.deck.path, local):
            if _mtime(local) != self.deck_mtime:  # PowerPoint에서 고치고 저장했으면 다시 읽는다
                if self.open_file(local, keep_position=True):
                    self.set_status("PowerPoint에서 저장한 내용을 다시 불러왔습니다.")
            return False
        return True if self.open_file(local) else None

    # ------------------------------------------------------------ 이벤트 처리 / 종료

    def _pump(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "tts":
                    _, kind, tag, info = ev
                    if kind == "done":
                        self._on_read_finished(tag, bool(info))
                    elif kind == "error":
                        self._on_read_finished(tag, False)
                        self.set_status(f"음성 재생 오류: {info}")
                elif ev[0] == "ppt" and self.link is not None:
                    self._on_ppt_state(ev[1])
                elif ev[0] == "ppt_error" and self.link is not None:
                    self.link_label.configure(text="연동 문제 발생")
                    self.set_status(ev[1])
        except queue.Empty:
            pass
        self.root.after(50, self._pump)

    def quit(self):
        self._commit_edit()
        _save_settings({
            "source": self.source,
            "voice": self.voice_var.get(),
            "output": {"id": self.output.id, "name": self.output.name} if self.output else None,
            "speed": round(self.speed_var.get(), 2),
            "auto_next": self.auto_next_var.get(),
            "read_on_change": self.read_on_change_var.get(),
            "topmost": self.topmost_var.get(),
        })
        if self.link:
            self.link.close()
        if self.speaker:
            self.speaker.close()
        self.root.destroy()


def _ui_family() -> str:
    if sys.platform == "win32":
        return "Malgun Gothic"
    if sys.platform == "darwin":
        return "Apple SD Gothic Neo"
    return "TkDefaultFont"


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _same_path(a, b) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _mtime(path) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_settings(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def run(initial_path: str | None = None):
    if sys.platform == "win32":
        try:  # 고해상도 화면에서 글자가 흐릿하지 않게
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    font.nametofont("TkDefaultFont").configure(family=_ui_family(),
                                               size=10 if sys.platform == "win32" else 13)
    App(root, initial_path)
    root.mainloop()

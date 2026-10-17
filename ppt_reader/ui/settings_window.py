"""설정 창: "발표 준비 n / 4"와 접히는 카드 네 장(발표 자료, 목소리, 질의응답, 캐릭터와 화면).

바꾸면 바로 저장하고 아래에 "저장됨"을 1.2초 띄운다. 적용·취소 단추는 없다. API 키는 [확인]을 누르거나 칸을 벗어날 때 저장한다.
설정을 바꾸는 일은 모두 controller를 거친다(강아지 바꾸기, 미리 만들기 다시 시작 같은 뒤따르는 일이 있어서).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..llm.base import MODELS
from ..settings import DOGS, ELEVENLABS_MODELS, GEMINI_TTS_MODELS
from ..slides import SOURCES
from ..voice.cloud import GEMINI_VOICES
from .widgets import Card, Chip, CoralBar, FitStack, Segmented, SittingDog, Toggle, button, field, label, row

TITLE = "설정 — PPT 읽어주기"
DOG_INFO = {"shiba": ("시바", "치비 시바"), "bichon": ("비숑", "몽실 비숑"), "beagle": ("비글", "날씬 비글")}
PROVIDER_LABELS = [("claude", "Claude"), ("openai", "OpenAI"), ("gemini", "Gemini")]
ENGINE_LABELS = [("os", "운영체제 음성"), ("elevenlabs", "ElevenLabs"), ("gemini", "Gemini")]
CUSTOM_MODEL = "직접 입력…"
KEY_EMPTY = "키를 넣고 [확인]을 누르세요"
KEY_CHECKING = "확인 중…"
KEY_OK = "✓ 키가 맞아요"
KEY_BAD = "✕ 키가 틀렸어요. 다시 확인하세요"
KEY_FAILED = "확인하지 못했어요: {reason}"
SAVED_MS = 1200


class KeyRow(QWidget):
    """API 키: 가린 칸, [보기]/[숨기기], [확인], 결과 글. owner는 키 주인(claude/openai/gemini/elevenlabs)."""

    def __init__(self, controller, owner: str):
        super().__init__()
        self.controller, self.owner = controller, owner
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_btn = button("보기", self._toggle_show, small=True)
        self.check_btn = button("확인", self.check, primary=True, small=True)
        line = QWidget()
        hl = QHBoxLayout(line)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(6)
        hl.addWidget(self.edit, 1)
        hl.addWidget(self.show_btn)
        hl.addWidget(self.check_btn)
        self.result = label("", "hint")
        lay.addWidget(line)
        lay.addWidget(self.result)
        self.edit.editingFinished.connect(self._save)  # 칸을 벗어날 때 저장
        self.set_owner(owner)

    def set_owner(self, owner: str) -> None:
        """키 주인이 바뀔 때만 칸을 다시 채운다(치는 중인 글과 확인 결과를 지우지 않게)."""
        settings = self.controller.settings
        if owner != getattr(self, "_shown_owner", None):
            self._shown_owner = owner
            self.owner = owner
            self.message = ""
            self.edit.setText(settings["keys"].get(owner, ""))
        self._show_state()

    def _show_state(self) -> None:
        settings = self.controller.settings
        if self.message:
            self.result.setText(self.message)
        elif settings["keys"].get(self.owner) and settings["key_ok"].get(self.owner):
            self.result.setText(KEY_OK)
        else:
            self.result.setText(KEY_EMPTY)

    def _toggle_show(self) -> None:
        hidden = self.edit.echoMode() == QLineEdit.EchoMode.Password
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self.show_btn.setText("숨기기" if hidden else "보기")

    def _save(self) -> None:
        key = self.edit.text().strip()
        if key != self.controller.settings["keys"].get(self.owner, ""):
            self.message = ""
            self.controller.set_key(self.owner, key)
            self._show_state()

    def check(self) -> None:
        self._save()
        key = self.edit.text().strip()
        if not key:
            self.message = ""
            self._show_state()
            return
        self.message = KEY_CHECKING
        self._show_state()
        owner = self.owner
        self.controller.check_key(owner, key, lambda ok, reason: self._checked(owner, ok, reason))

    def _checked(self, owner: str, ok: bool | None, reason: str) -> None:
        if owner != self.owner:
            return
        self.message = KEY_FAILED.format(reason=reason) if ok is None else (KEY_OK if ok else KEY_BAD)
        self._show_state()


class DeviceCombo(QComboBox):
    """목록을 펼 때마다 연결된 장치를 다시 찾는다(나중에 연결한 블루투스 이어폰도 고를 수 있게)."""

    def __init__(self, on_popup):
        super().__init__()
        self._on_popup = on_popup

    def showPopup(self):
        self._on_popup()
        super().showPopup()


class SettingsWindow(QWidget):
    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Window)
        self.controller = controller
        self.settings = controller.settings
        self.setObjectName("settingsRoot")
        self.setWindowTitle(TITLE)
        self.resize(720, 680)
        self._building = 0  # 화면을 다시 채우는 중(깊이). 이때 오는 값 바뀜 신호는 저장하지 않는다
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("settingsScroll")
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.lay = QVBoxLayout(content)
        self.lay.setContentsMargins(22, 20, 22, 22)
        self.lay.setSpacing(12)
        self._build_hero()
        self.cards = [Card(1, "발표 자료"), Card(2, "목소리"), Card(3, "질의응답"), Card(4, "캐릭터와 화면")]
        self._build_deck(self.cards[0])
        self._build_voice(self.cards[1])
        self._build_qa(self.cards[2])
        self._build_character(self.cards[3])
        for c in self.cards:
            self.lay.addWidget(c)
        foot = QWidget()
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(0, 6, 0, 0)
        fl.addStretch(1)
        fl.addWidget(label("바꾸면 바로 저장돼요", "hint"))
        lic = QPushButton("오픈 소스 라이선스")
        lic.setObjectName("link")
        lic.setCursor(Qt.CursorShape.PointingHandCursor)
        lic.clicked.connect(lambda: controller.open_licenses())
        fl.addWidget(lic)
        fl.addStretch(1)
        self.lay.addWidget(foot)
        self.lay.addStretch(1)
        self.toast = QLabel("저장됨", self)
        self.toast.setObjectName("toast")
        self.toast.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.toast.hide)
        self.refresh()

    # ------------------------------------------------------------ 머리

    def _build_hero(self) -> None:
        hero = QWidget()
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(4, 0, 0, 6)
        hl.setSpacing(16)
        self.hero_dog = SittingDog(self.settings["dog"], 96)
        hl.addWidget(self.hero_dog)
        col = QWidget()
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        self.hero_title = label("", "heroTitle")
        chips = QWidget()
        chl = QHBoxLayout(chips)
        chl.setContentsMargins(0, 0, 0, 0)
        chl.setSpacing(6)
        self.hero_chips = [Chip() for _ in range(4)]
        for chip in self.hero_chips:
            chl.addWidget(chip)
        chl.addStretch(1)
        self.hero_bar = CoralBar()
        cl.addWidget(self.hero_title)
        cl.addWidget(chips)
        cl.addWidget(self.hero_bar)
        hl.addWidget(col, 1)
        self.lay.addWidget(hero)

    # ------------------------------------------------------------ 카드 1: 발표 자료

    def _build_deck(self, card: Card) -> None:
        c = self.controller
        self.deck_stack = FitStack()
        empty = QWidget()
        el = QHBoxLayout(empty)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(10)
        el.addWidget(button("파일 열기…", c.open_file_dialog, primary=True))
        el.addWidget(label("또는 PowerPoint에 자료를 열고 연동을 켜세요", "hint"), 1)
        has = QWidget()
        hl = QHBoxLayout(has)
        hl.setContentsMargins(0, 0, 0, 0)
        info = QWidget()
        il = QVBoxLayout(info)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(2)
        self.deck_name = label("")
        self.deck_name.setStyleSheet("font-weight: 700;")
        self.deck_counts = label("", "hint")
        il.addWidget(self.deck_name)
        il.addWidget(self.deck_counts)
        hl.addWidget(info, 1)
        hl.addWidget(button("다른 파일…", c.open_file_dialog, small=True))
        hl.addWidget(button("📝 대본 열기", c.open_script_window, primary=True, small=True))
        self.deck_stack.addWidget(empty)
        self.deck_stack.addWidget(has)
        self.link_chip = Chip()
        self.link_toggle = Toggle(False)
        self.link_toggle.toggled.connect(lambda on: None if self._building else c.set_link(on))
        self.source_box = QComboBox()
        self.source_box.addItems([lab for _, lab in SOURCES])
        self.source_box.currentIndexChanged.connect(
            lambda i: None if self._building else self._apply(source=SOURCES[i][0]))
        self.source_field = field("읽을 내용", self.source_box)
        card.body_layout.addWidget(self.deck_stack)
        card.body_layout.addWidget(row(label("PowerPoint 연동"), self.link_chip, self.link_toggle, stretch_after=0))
        card.body_layout.addWidget(self.source_field)

    # ------------------------------------------------------------ 카드 2: 목소리

    def _build_voice(self, card: Card) -> None:
        c = self.controller
        self.engine_seg = Segmented(ENGINE_LABELS, self.settings["voice_engine"])
        self.engine_seg.changed.connect(lambda k: self._apply(voice_engine=k))
        card.body_layout.addWidget(field("목소리 엔진", self.engine_seg))
        self.engine_stack = FitStack()
        # 운영체제 음성
        self.os_voice = QComboBox()
        self.os_voice.currentIndexChanged.connect(
            lambda _i: None if self._building else self._apply(voice=self.os_voice.currentData() or ""))
        os_page = field("목소리", row(self.os_voice, button("들어 보기", c.preview_voice, small=True), grow=0))
        # ElevenLabs
        self.el_voice = QComboBox()
        self.el_voice.currentIndexChanged.connect(lambda _i: None if self._building else self._apply_el_voice())
        self.el_model = QComboBox()
        self.el_model.addItems(list(ELEVENLABS_MODELS))
        self.el_model.currentTextChanged.connect(lambda m: None if self._building else self._apply_cloud("elevenlabs", model=m))
        self.el_key = KeyRow(c, "elevenlabs")
        self.el_progress = label("", "hint")
        el_page = QWidget()
        ell = QVBoxLayout(el_page)
        ell.setContentsMargins(0, 0, 0, 0)
        ell.setSpacing(10)
        ell.addWidget(field("목소리", row(self.el_voice, button("들어 보기", c.preview_voice, small=True), grow=0)))
        ell.addWidget(field("모델", self.el_model))
        ell.addWidget(field("API 키", self.el_key))
        ell.addWidget(label("ElevenLabs 무료 등급은 한 달에 약 1만 자예요. 미리 만들기에도 글자 수가 들어요.", "hint"))
        ell.addWidget(self.el_progress)
        # Gemini
        self.gm_voice = QComboBox()
        self.gm_voice.addItems(list(GEMINI_VOICES))
        self.gm_voice.currentTextChanged.connect(lambda v: None if self._building else self._apply_cloud("gemini", voice=v))
        self.gm_model = QComboBox()
        self.gm_model.addItems(list(GEMINI_TTS_MODELS))
        self.gm_model.currentTextChanged.connect(lambda m: None if self._building else self._apply_cloud("gemini", model=m))
        self.gm_key = KeyRow(c, "gemini")
        self.gm_progress = label("", "hint")
        gm_page = QWidget()
        gml = QVBoxLayout(gm_page)
        gml.setContentsMargins(0, 0, 0, 0)
        gml.setSpacing(10)
        gml.addWidget(field("목소리", row(self.gm_voice, button("들어 보기", c.preview_voice, small=True), grow=0)))
        gml.addWidget(field("모델", self.gm_model))
        gml.addWidget(field("API 키", self.gm_key, hint="질의응답의 Gemini 키와 같아요"))
        gml.addWidget(self.gm_progress)
        for page in (os_page, el_page, gm_page):
            self.engine_stack.addWidget(page)
        card.body_layout.addWidget(self.engine_stack)
        self.cloud_notice = label("키를 확인하기 전까지는 운영체제 음성으로 읽어요", "hint")
        card.body_layout.addWidget(self.cloud_notice)
        self.output_box = DeviceCombo(self._fill_outputs)
        self.output_box.currentIndexChanged.connect(lambda _i: None if self._building else self._apply_output())
        card.body_layout.addWidget(field("출력 장치", self.output_box))
        self.auto_toggle = Toggle(self.settings["auto_next"])
        self.auto_toggle.toggled.connect(lambda on: self._apply(auto_next=on))
        self.show_toggle = Toggle(self.settings["read_on_change"])
        self.show_toggle.toggled.connect(lambda on: self._apply(read_on_change=on))
        card.body_layout.addWidget(row(label("다 읽으면 다음 장으로 넘어가기 (자동 발표)"), self.auto_toggle, stretch_after=0))
        card.body_layout.addWidget(row(label("쇼에서 장을 넘기면 바로 읽기"), self.show_toggle, stretch_after=0))
        card.body_layout.addWidget(label("배속은 원 버튼의 위성 버튼에서 바꿔요.", "hint"))

    # ------------------------------------------------------------ 카드 3: 질의응답

    def _build_qa(self, card: Card) -> None:
        c = self.controller
        self.provider_seg = Segmented(PROVIDER_LABELS, self.settings["provider"])
        self.provider_seg.changed.connect(self._change_provider)
        card.body_layout.addWidget(field("AI 제공자", self.provider_seg))
        self.model_box = QComboBox()
        self.model_box.currentIndexChanged.connect(lambda _i: None if self._building else self._choose_model())
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("모델 id")
        self.model_edit.editingFinished.connect(self._custom_model)
        card.body_layout.addWidget(field("모델", self.model_box, self.model_edit))
        self.qa_key = KeyRow(c, self.settings["provider"])
        card.body_layout.addWidget(field("API 키", self.qa_key))
        self.persona = QPlainTextEdit()
        self.persona.setFixedHeight(80)
        self.persona.setPlainText(self.settings["persona"])
        self.persona.textChanged.connect(lambda: self._persona_timer.start())
        self._persona_timer = QTimer(self)
        self._persona_timer.setSingleShot(True)
        self._persona_timer.setInterval(600)
        self._persona_timer.timeout.connect(lambda: self._apply(persona=self.persona.toPlainText()))
        card.body_layout.addWidget(field("개인 지침", self.persona, hint="모든 답에 반영돼요"))
        self.caption_toggle = Toggle(self.settings["captions"])
        self.caption_toggle.toggled.connect(lambda on: self._apply(captions=on))
        cap = QWidget()
        capl = QHBoxLayout(cap)
        capl.setContentsMargins(0, 0, 0, 0)
        capl.addWidget(label("그림 설명(캡션) 만들기"))
        cap_hint = label("질의응답 근거로만 씀 · 요금이 조금 듦", "hint")
        cap_hint.setWordWrap(False)
        capl.addWidget(cap_hint)
        capl.addStretch(1)
        capl.addWidget(self.caption_toggle)
        card.body_layout.addWidget(cap)

    # ------------------------------------------------------------ 카드 4: 캐릭터와 화면

    def _build_character(self, card: Card) -> None:
        dogs = QWidget()
        dl = QHBoxLayout(dogs)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(10)
        self.dog_cards: dict[str, QPushButton] = {}
        for key in DOGS:
            short, long_ = DOG_INFO[key]
            b = QPushButton()
            b.setObjectName("slideCard")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            bl = QVBoxLayout(b)
            bl.setContentsMargins(8, 6, 8, 6)
            bl.addWidget(SittingDog(key, 72), 0, Qt.AlignmentFlag.AlignHCenter)
            bl.addWidget(label(short + (" · 기본" if key == "shiba" else "")), 0, Qt.AlignmentFlag.AlignHCenter)
            bl.addWidget(label(long_, "hint"), 0, Qt.AlignmentFlag.AlignHCenter)
            b.setFixedSize(140, 150)
            b.clicked.connect(lambda _c=False, k=key: self._apply(dog=k))
            self.dog_cards[key] = b
            dl.addWidget(b)
        dl.addStretch(1)
        card.body_layout.addWidget(field("강아지", dogs))
        self.dog_toggle = Toggle(self.settings["dog_visible"])
        self.dog_toggle.toggled.connect(lambda on: self._apply(dog_visible=on))
        card.body_layout.addWidget(row(label("강아지 보이기"), self.dog_toggle, stretch_after=0))
        self.monitor_box = QComboBox()
        self.monitor_box.currentIndexChanged.connect(
            lambda _i: None if self._building else self._apply(monitor=self.monitor_box.currentData() or "follow"))
        card.body_layout.addWidget(field("원 버튼 모니터", self.monitor_box, hint="강아지도 이 모니터에서만 다녀요"))

    # ------------------------------------------------------------ 바꾸기

    def _apply(self, **values) -> None:
        if self._building:
            return
        self.controller.apply(**values)
        self.saved()
        self.refresh()

    def _apply_cloud(self, engine: str, **fields) -> None:
        cloud = {**self.settings["cloud_voice"]}
        cloud[engine] = {**cloud[engine], **fields}
        self._apply(cloud_voice=cloud)

    def _apply_el_voice(self) -> None:
        vid = self.el_voice.currentData() or ""
        self._apply_cloud("elevenlabs", voice_id=vid, voice_name=self.el_voice.currentText() if vid else "")

    def _apply_output(self) -> None:
        out = self.output_box.currentData()
        self._apply(output={"id": out.id, "name": out.name} if out else None)

    def _change_provider(self, provider: str) -> None:
        self._apply(provider=provider)
        self.qa_key.set_owner(provider)

    def _choose_model(self) -> None:
        data = self.model_box.currentData()
        custom = data == CUSTOM_MODEL
        self.model_edit.setVisible(custom)
        if not custom and data:
            models = {**self.settings["models"], self.settings["provider"]: data}
            self._apply(models=models)

    def _custom_model(self) -> None:
        text = self.model_edit.text().strip()
        if text:
            self._apply(models={**self.settings["models"], self.settings["provider"]: text})

    def saved(self) -> None:
        """아래에 "저장됨"을 1.2초 띄운다."""
        self.toast.adjustSize()
        self.toast.move((self.width() - self.toast.width()) // 2, self.height() - self.toast.height() - 14)
        self.toast.raise_()
        self.toast.show()
        self._toast_timer.start(SAVED_MS)

    # ------------------------------------------------------------ 보이기

    def _fill_outputs(self) -> None:
        self._building += 1
        self.output_box.clear()
        default_label, outputs, chosen = self.controller.output_choices()
        self.output_box.addItem(default_label, None)
        index = 0
        for out, text in outputs:
            self.output_box.addItem(text, out)
            if chosen is not None and out.id == chosen.id:
                index = self.output_box.count() - 1
        self.output_box.setCurrentIndex(index)
        self._building -= 1

    def steps(self) -> list[tuple[str, bool, str]]:
        """카드마다 (이름, 끝남, 요약)."""
        s, c = self.settings, self.controller
        deck = c.session.deck
        engine = s["voice_engine"]
        voice_done = engine == "os" or bool(s["key_ok"].get(engine))
        qa_done = bool(s["key_ok"].get(s["provider"]))
        engine_name = dict(ENGINE_LABELS)[engine]
        return [
            ("발표 자료", deck is not None, f"{deck.name} · {c.link_chip_state()[0]}" if deck else "아직 열지 않았어요"),
            ("목소리", voice_done, engine_name),
            ("질의응답", qa_done, f"{dict(PROVIDER_LABELS)[s['provider']]} · {s['models'][s['provider']]} · "
                               f"캡션 {'켬' if s['captions'] else '끔'}"),
            ("캐릭터와 화면", True, f"{DOG_INFO[s['dog']][0]} · {'보임' if s['dog_visible'] else '숨김'}"),
        ]

    def open_cards(self, first_run: bool) -> None:
        """처음 실행 때는 아직 안 된 첫 카드만, 평소에는 발표 자료 카드만 펼친다."""
        steps = self.steps()
        nxt = next((i for i, (_, done, _) in enumerate(steps) if not done), None)
        for i, card in enumerate(self.cards):
            card.set_open(i == nxt if first_run and nxt is not None else i == 0)

    def refresh(self) -> None:
        self._building += 1
        try:
            self._refresh()
        finally:
            self._building -= 1

    def _refresh(self) -> None:
        s, c = self.settings, self.controller
        steps = self.steps()
        done = sum(1 for _, d, _ in steps if d)
        self.hero_title.setText("발표 준비 끝! 🎉" if done == 4 else f"발표 준비 {done} / 4")
        for chip, (name, d, _) in zip(self.hero_chips, steps):
            chip.set(f"{'✓' if d else '!'} {name}", "ok" if d else "bad")
        self.hero_bar.set_value(done / 4)
        self.hero_dog.set_dog(s["dog"])
        nxt = next((i for i, (_, d, _) in enumerate(steps) if not d), None)
        for i, (card, (_, d, summary)) in enumerate(zip(self.cards, steps)):
            card.set_state(d, i == nxt, summary)
        # 카드 1
        deck = c.session.deck
        self.deck_stack.setCurrentIndex(1 if deck else 0)
        self.source_field.setVisible(deck is not None)
        if deck:
            notes = sum(1 for sl in deck.slides if sl.notes)
            self.deck_name.setText(deck.name)
            self.deck_counts.setText(f"슬라이드 {len(deck.slides)}장 · 노트 있는 장 {notes}개 · 고친 대본 {len(c.session.edits)}장")
        self.link_toggle.setChecked(c.session.link is not None)
        self.link_chip.set(*c.link_chip_state())
        self.source_box.setCurrentIndex([k for k, _ in SOURCES].index(s["source"]))
        # 카드 2
        engine = s["voice_engine"]
        self.engine_seg.set_current(engine)
        self.engine_stack.setCurrentIndex([k for k, _ in ENGINE_LABELS].index(engine))
        self.cloud_notice.setVisible(engine != "os" and not s["key_ok"].get(engine))
        self.os_voice.clear()
        for vid, text, name in c.os_voices():
            self.os_voice.addItem(text, name)
        names = [self.os_voice.itemData(i) for i in range(self.os_voice.count())]
        if s["voice"] in names:
            self.os_voice.setCurrentIndex(names.index(s["voice"]))
        conf = s["cloud_voice"]
        self.el_voice.clear()
        for v in c.elevenlabs_voices():
            self.el_voice.addItem(v.name, v.id)
        if conf["elevenlabs"]["voice_id"] and self.el_voice.findData(conf["elevenlabs"]["voice_id"]) < 0:
            self.el_voice.addItem(conf["elevenlabs"]["voice_name"] or conf["elevenlabs"]["voice_id"],
                                  conf["elevenlabs"]["voice_id"])
        self.el_voice.setCurrentIndex(max(0, self.el_voice.findData(conf["elevenlabs"]["voice_id"])))
        self.el_model.setCurrentText(conf["elevenlabs"]["model"])
        self.gm_voice.setCurrentText(conf["gemini"]["voice"])
        self.gm_model.setCurrentText(conf["gemini"]["model"])
        progress = c.presynth_text()
        self.el_progress.setText(progress)
        self.gm_progress.setText(progress)
        self.gm_key.set_owner("gemini")
        self.el_key.set_owner("elevenlabs")
        self._fill_outputs()
        self.auto_toggle.setChecked(s["auto_next"])
        self.show_toggle.setChecked(s["read_on_change"])
        # 카드 3
        provider = s["provider"]
        self.provider_seg.set_current(provider)
        self.qa_key.set_owner(provider)
        self.model_box.clear()
        model = s["models"][provider]
        for m in MODELS[provider]:
            self.model_box.addItem(f"{m} (기본)" if m == MODELS[provider][0] else m, m)
        self.model_box.addItem(CUSTOM_MODEL, CUSTOM_MODEL)
        if model in MODELS[provider]:
            self.model_box.setCurrentIndex(MODELS[provider].index(model))
            self.model_edit.hide()
        else:
            self.model_box.setCurrentIndex(self.model_box.count() - 1)
            self.model_edit.setText(model)
            self.model_edit.show()
        self.caption_toggle.setChecked(s["captions"])
        # 카드 4
        for key, b in self.dog_cards.items():
            b.setChecked(key == s["dog"])
        self.dog_toggle.setChecked(s["dog_visible"])
        self.monitor_box.clear()
        for value, text in c.monitor_choices():
            self.monitor_box.addItem(text, value)
        idx = self.monitor_box.findData(s["monitor"])
        self.monitor_box.setCurrentIndex(max(0, idx))

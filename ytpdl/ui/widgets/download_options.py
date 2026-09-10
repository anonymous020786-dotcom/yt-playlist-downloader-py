"""The download-options form.

A single panel that edits a :class:`DownloadSettings`. Used both on the Home page
(as a collapsible "Options" drawer) and, conceptually, anywhere a job's settings
need review. Call :meth:`load` to populate from a settings object and
:meth:`apply` to write the widget state back into one.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ... import config
from ...core.settings import DownloadSettings
from ...i18n import tr


class DownloadOptions(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._build()
        self._wire()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        # --- format row -------------------------------------------------
        fmt = QFormLayout()
        fmt.setSpacing(10)

        self.audio_only = QCheckBox(tr("AudioOnly"))
        self.audio_format = QComboBox()
        self.audio_format.addItems(config.AUDIO_FORMATS)
        self.video_format = QComboBox()
        self.video_format.addItems(config.VIDEO_FORMATS)
        self.quality = QComboBox()
        self.quality.addItems([f"{r}p" for r in config.RESOLUTIONS])

        fmt_box = QWidget()
        fmt_lay = QHBoxLayout(fmt_box)
        fmt_lay.setContentsMargins(0, 0, 0, 0)
        fmt_lay.addWidget(self.video_format)
        fmt_lay.addWidget(self.audio_format)
        fmt_lay.addWidget(self.quality)

        fmt.addRow(self.audio_only)
        fmt.addRow(QLabel(tr("Format")), fmt_box)

        self.prefer_fps = QCheckBox(tr("Prefer") + " (FPS)")
        self.convert = QCheckBox(tr("Convert"))
        self.set_bitrate = QCheckBox(tr("BitRate"))
        self.bitrate = QLineEdit()
        self.bitrate.setPlaceholderText("192")
        self.bitrate.setMaximumWidth(90)
        br_box = QWidget()
        br_lay = QHBoxLayout(br_box)
        br_lay.setContentsMargins(0, 0, 0, 0)
        br_lay.addWidget(self.set_bitrate)
        br_lay.addWidget(self.bitrate)
        br_lay.addWidget(QLabel("kbit/s"))
        br_lay.addStretch(1)

        fmt.addRow(self.prefer_fps)
        fmt.addRow(self.convert)
        fmt.addRow(br_box)
        root.addLayout(fmt)

        # --- toggles --------------------------------------------------
        self.tag_audio = QCheckBox(tr("TagAudio"))
        self.embed_thumb = QCheckBox(tr("EmbedThumbnail"))
        self.separate_folders = QCheckBox(tr("SeparateFolders"))
        self.skip_existing = QCheckBox(tr("SkipExisting"))
        self.open_when_done = QCheckBox(tr("OpenWhenDone"))
        for cb in (self.tag_audio, self.embed_thumb, self.separate_folders,
                   self.skip_existing, self.open_when_done):
            root.addWidget(cb)

        # --- subtitles ----------------------------------------------
        self.subs = QCheckBox(tr("DownloadCaptions"))
        self.auto_subs = QCheckBox(tr("AutoSubtitles"))
        self.embed_subs = QCheckBox(tr("EmbedSubtitles"))
        self.sub_langs = QLineEdit()
        self.sub_langs.setPlaceholderText("en, es, fr")
        subs_form = QFormLayout()
        subs_form.setSpacing(8)
        subs_form.addRow(self.subs)
        subs_form.addRow(QLabel(tr("SubtitleLanguages")), self.sub_langs)
        subs_form.addRow(self.auto_subs)
        subs_form.addRow(self.embed_subs)
        root.addLayout(subs_form)

        # --- filename template ------------------------------------
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("$title")
        fn_form = QFormLayout()
        fn_form.setSpacing(6)
        fn_form.addRow(QLabel(tr("FilenameTemplate")), self.filename)
        hint = QLabel(tr("FilenameTemplateHint"))
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        fn_form.addRow(hint)
        root.addLayout(fn_form)

        # --- subset --------------------------------------------------
        self.use_subset = QCheckBox(tr("SubsetRange"))
        self.subset_start = QSpinBox()
        self.subset_start.setRange(1, 999999)
        self.subset_end = QSpinBox()
        self.subset_end.setRange(0, 999999)
        self.subset_end.setSpecialValueText("∞")
        subset_box = QWidget()
        sb = QHBoxLayout(subset_box)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.addWidget(self.use_subset)
        sb.addWidget(QLabel("#"))
        sb.addWidget(self.subset_start)
        sb.addWidget(QLabel("→"))
        sb.addWidget(self.subset_end)
        sb.addStretch(1)
        root.addWidget(subset_box)

        # --- length filter ---------------------------------------
        self.filter_len = QCheckBox(tr("FilterByLength"))
        self.filter_shorter = QRadioButton(tr("Shorter"))
        self.filter_longer = QRadioButton(tr("Longer"))
        self.filter_shorter.setChecked(True)
        self.filter_minutes = QDoubleSpinBox()
        self.filter_minutes.setRange(0.1, 999.0)
        self.filter_minutes.setValue(4.0)
        self.filter_minutes.setSuffix(" min")
        fl_box = QWidget()
        fl = QHBoxLayout(fl_box)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(self.filter_len)
        fl.addWidget(self.filter_shorter)
        fl.addWidget(self.filter_longer)
        fl.addWidget(self.filter_minutes)
        fl.addStretch(1)
        root.addWidget(fl_box)

        self._sync_enabled()

    # ------------------------------------------------------------------- wire
    def _wire(self) -> None:
        widgets = [
            self.audio_only, self.prefer_fps, self.convert, self.set_bitrate,
            self.tag_audio, self.embed_thumb, self.separate_folders,
            self.skip_existing, self.open_when_done, self.subs, self.auto_subs,
            self.embed_subs, self.use_subset, self.filter_len,
            self.filter_shorter, self.filter_longer,
        ]
        for w in widgets:
            w.toggled.connect(self._on_change)
        for combo in (self.audio_format, self.video_format, self.quality):
            combo.currentIndexChanged.connect(self._on_change)
        for edit in (self.bitrate, self.sub_langs, self.filename):
            edit.editingFinished.connect(self.changed)
        for spin in (self.subset_start, self.subset_end, self.filter_minutes):
            spin.valueChanged.connect(self.changed)

    def _on_change(self, *_a) -> None:
        self._sync_enabled()
        self.changed.emit()

    def _sync_enabled(self) -> None:
        audio = self.audio_only.isChecked()
        self.video_format.setEnabled(not audio)
        self.quality.setEnabled(not audio)
        self.prefer_fps.setEnabled(not audio)
        self.audio_format.setEnabled(audio or self.convert.isChecked())
        self.bitrate.setEnabled(self.set_bitrate.isChecked())
        self.sub_langs.setEnabled(self.subs.isChecked())
        self.auto_subs.setEnabled(self.subs.isChecked())
        self.embed_subs.setEnabled(self.subs.isChecked() and not audio)
        self.subset_start.setEnabled(self.use_subset.isChecked())
        self.subset_end.setEnabled(self.use_subset.isChecked())
        self.filter_shorter.setEnabled(self.filter_len.isChecked())
        self.filter_longer.setEnabled(self.filter_len.isChecked())
        self.filter_minutes.setEnabled(self.filter_len.isChecked())

    # ------------------------------------------------------------- transfer
    def load(self, s: DownloadSettings) -> None:
        self.audio_only.setChecked(s.audio_only)
        self.audio_format.setCurrentText(s.audio_format)
        self.video_format.setCurrentText(s.video_format)
        self.quality.setCurrentText(f"{s.quality}p")
        self.prefer_fps.setChecked(s.prefer_highest_fps)
        self.convert.setChecked(s.convert)
        self.set_bitrate.setChecked(s.set_bitrate)
        self.bitrate.setText(s.bitrate)
        self.tag_audio.setChecked(s.tag_audio)
        self.embed_thumb.setChecked(s.embed_thumbnail)
        self.separate_folders.setChecked(s.separate_playlist_folders)
        self.skip_existing.setChecked(s.skip_existing)
        self.open_when_done.setChecked(s.open_folder_when_done)
        self.subs.setChecked(s.download_subtitles)
        self.auto_subs.setChecked(s.auto_subtitles)
        self.embed_subs.setChecked(s.embed_subtitles)
        self.sub_langs.setText(s.subtitle_languages)
        self.filename.setText(s.filename_template)
        self.use_subset.setChecked(s.use_subset)
        self.subset_start.setValue(max(1, s.subset_start))
        self.subset_end.setValue(max(0, s.subset_end))
        self.filter_len.setChecked(s.filter_by_length)
        self.filter_longer.setChecked(s.filter_longer_than)
        self.filter_shorter.setChecked(not s.filter_longer_than)
        self.filter_minutes.setValue(s.filter_minutes)
        self._sync_enabled()

    def apply(self, s: DownloadSettings) -> None:
        s.audio_only = self.audio_only.isChecked()
        s.audio_format = self.audio_format.currentText()
        s.video_format = self.video_format.currentText()
        s.quality = self.quality.currentText().rstrip("p")
        s.prefer_highest_fps = self.prefer_fps.isChecked()
        s.convert = self.convert.isChecked()
        s.set_bitrate = self.set_bitrate.isChecked()
        s.bitrate = self.bitrate.text().strip() or "192"
        s.tag_audio = self.tag_audio.isChecked()
        s.embed_thumbnail = self.embed_thumb.isChecked()
        s.separate_playlist_folders = self.separate_folders.isChecked()
        s.skip_existing = self.skip_existing.isChecked()
        s.open_folder_when_done = self.open_when_done.isChecked()
        s.download_subtitles = self.subs.isChecked()
        s.auto_subtitles = self.auto_subs.isChecked()
        s.embed_subtitles = self.embed_subs.isChecked()
        s.subtitle_languages = self.sub_langs.text().strip() or "en"
        s.filename_template = self.filename.text().strip() or "$title"
        s.use_subset = self.use_subset.isChecked()
        s.subset_start = self.subset_start.value()
        s.subset_end = self.subset_end.value()
        s.filter_by_length = self.filter_len.isChecked()
        s.filter_longer_than = self.filter_longer.isChecked()
        s.filter_minutes = self.filter_minutes.value()

"""The download-options form.

A single panel that edits a :class:`DownloadSettings`, laid out as a handful of
labelled sections rather than one long column of checkboxes. Used on the Home
page inside a collapsible drawer. Call :meth:`load` to populate from a settings
object and :meth:`apply` to write the widget state back into one.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
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


def _section(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Inset")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(12)
    head = QLabel(title.upper())
    head.setObjectName("SectionLabel")
    lay.addWidget(head)
    return frame, lay


class DownloadOptions(QWidget):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._build()
        self._wire()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(14)

        root.addWidget(self._format_section())
        root.addWidget(self._output_section())
        root.addWidget(self._subtitles_section())
        root.addWidget(self._selection_section())
        root.addStretch(1)
        self._sync_enabled()

    def _format_section(self) -> QFrame:
        frame, lay = _section(tr("FileConversion"))

        self.mode_video = QRadioButton(tr("Video"))
        self.mode_audio = QRadioButton(tr("Audio"))
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.mode_video)
        self._mode_group.addButton(self.mode_audio)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(16)
        mode_row.addWidget(self.mode_video)
        mode_row.addWidget(self.mode_audio)
        mode_row.addStretch(1)
        lay.addLayout(mode_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.video_format = QComboBox()
        self.video_format.addItems(config.VIDEO_FORMATS)
        self.quality = QComboBox()
        self.quality.addItems([f"{r}p" for r in config.RESOLUTIONS])
        self.audio_format = QComboBox()
        self.audio_format.addItems(config.AUDIO_FORMATS)

        self._lbl_container = QLabel(tr("SaveVideoFormat"))
        self._lbl_quality = QLabel(tr("Prefer"))
        self._lbl_audio = QLabel(tr("ConvertToMp3"))
        grid.addWidget(self._lbl_container, 0, 0)
        grid.addWidget(self.video_format, 0, 1)
        grid.addWidget(self._lbl_quality, 1, 0)
        grid.addWidget(self.quality, 1, 1)
        grid.addWidget(self._lbl_audio, 2, 0)
        grid.addWidget(self.audio_format, 2, 1)
        lay.addLayout(grid)

        self.prefer_fps = QCheckBox(tr("PreferFPS"))
        self.convert = QCheckBox(tr("Convert"))
        lay.addWidget(self.prefer_fps)
        lay.addWidget(self.convert)

        br_row = QHBoxLayout()
        br_row.setSpacing(8)
        self.set_bitrate = QCheckBox(tr("BitRate"))
        self.bitrate = QLineEdit()
        self.bitrate.setPlaceholderText("192")
        self.bitrate.setMaximumWidth(80)
        br_row.addWidget(self.set_bitrate)
        br_row.addWidget(self.bitrate)
        br_row.addWidget(QLabel("kbit/s"))
        br_row.addStretch(1)
        lay.addLayout(br_row)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        lang_row.addWidget(QLabel(tr("VideoLanguage")))
        self.audio_language = QLineEdit()
        self.audio_language.setPlaceholderText("default")
        self.audio_language.setMaximumWidth(140)
        lang_row.addWidget(self.audio_language)
        lang_row.addStretch(1)
        lay.addLayout(lang_row)
        return frame

    def _output_section(self) -> QFrame:
        frame, lay = _section(tr("Options"))
        self.tag_audio = QCheckBox(tr("TagAudio"))
        self.embed_thumb = QCheckBox(tr("EmbedThumbnail"))
        self.separate_folders = QCheckBox(tr("SavePlaylistInUniqueDirectory"))
        self.skip_existing = QCheckBox(tr("SkipExisting"))
        self.open_when_done = QCheckBox(tr("OpenDestinationFolderOnFinish"))
        for cb in (self.tag_audio, self.embed_thumb, self.separate_folders,
                   self.skip_existing, self.open_when_done):
            lay.addWidget(cb)

        lay.addWidget(QLabel(tr("FileNamePattern")))
        self.filename = QLineEdit()
        self.filename.setPlaceholderText("$title")
        lay.addWidget(self.filename)
        hint = QLabel(tr("FilenameTemplateHint"))
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return frame

    def _subtitles_section(self) -> QFrame:
        frame, lay = _section(tr("DownloadCaptions"))
        self.subs = QCheckBox(tr("DownloadCaptions"))
        self.auto_subs = QCheckBox(tr("AutoSubtitles"))
        self.embed_subs = QCheckBox(tr("EmbedSubtitles"))
        lay.addWidget(self.subs)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel(tr("CaptionsLanguage")))
        self.sub_langs = QLineEdit()
        self.sub_langs.setPlaceholderText("en, es, fr")
        row.addWidget(self.sub_langs, 1)
        lay.addLayout(row)
        lay.addWidget(self.auto_subs)
        lay.addWidget(self.embed_subs)
        return frame

    def _selection_section(self) -> QFrame:
        frame, lay = _section(tr("DownloadFilter"))

        self.use_subset = QCheckBox(tr("SubsetRange"))
        lay.addWidget(self.use_subset)
        subset_row = QHBoxLayout()
        subset_row.setSpacing(8)
        self.subset_start = QSpinBox()
        self.subset_start.setRange(1, 999999)
        self.subset_end = QSpinBox()
        self.subset_end.setRange(0, 999999)
        self.subset_end.setSpecialValueText("∞")
        subset_row.addWidget(QLabel(tr("PlaylistIndex")))
        subset_row.addWidget(self.subset_start)
        subset_row.addWidget(QLabel(tr("UntilIndex")))
        subset_row.addWidget(self.subset_end)
        subset_row.addStretch(1)
        lay.addLayout(subset_row)

        self.filter_len = QCheckBox(tr("FilterByLength"))
        lay.addWidget(self.filter_len)
        flt_row = QHBoxLayout()
        flt_row.setSpacing(8)
        self.filter_shorter = QRadioButton(tr("Shorter"))
        self.filter_longer = QRadioButton(tr("Longer"))
        self.filter_shorter.setChecked(True)
        self._len_group = QButtonGroup(self)
        self._len_group.addButton(self.filter_shorter)
        self._len_group.addButton(self.filter_longer)
        self.filter_minutes = QDoubleSpinBox()
        self.filter_minutes.setRange(0.1, 999.0)
        self.filter_minutes.setValue(4.0)
        self.filter_minutes.setSuffix(f" {tr('Minutes')}")
        flt_row.addWidget(self.filter_shorter)
        flt_row.addWidget(self.filter_longer)
        flt_row.addWidget(self.filter_minutes)
        flt_row.addStretch(1)
        lay.addLayout(flt_row)
        return frame

    # ------------------------------------------------------------------- wire
    def _wire(self) -> None:
        toggles = [
            self.mode_audio, self.mode_video, self.prefer_fps, self.convert,
            self.set_bitrate, self.tag_audio, self.embed_thumb,
            self.separate_folders, self.skip_existing, self.open_when_done,
            self.subs, self.auto_subs, self.embed_subs, self.use_subset,
            self.filter_len, self.filter_shorter, self.filter_longer,
        ]
        for w in toggles:
            w.toggled.connect(self._on_change)
        for combo in (self.audio_format, self.video_format, self.quality):
            combo.currentIndexChanged.connect(self._on_change)
        for edit in (self.bitrate, self.sub_langs, self.filename, self.audio_language):
            edit.editingFinished.connect(self.changed)
        for spin in (self.subset_start, self.subset_end, self.filter_minutes):
            spin.valueChanged.connect(self.changed)

    def _on_change(self, *_a) -> None:
        self._sync_enabled()
        self.changed.emit()

    def _sync_enabled(self) -> None:
        audio = self.mode_audio.isChecked()
        self._lbl_container.setEnabled(not audio)
        self.video_format.setEnabled(not audio)
        self._lbl_quality.setEnabled(not audio)
        self.quality.setEnabled(not audio)
        self.prefer_fps.setEnabled(not audio)
        self._lbl_audio.setEnabled(audio or self.convert.isChecked())
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
        self.mode_audio.setChecked(s.audio_only)
        self.mode_video.setChecked(not s.audio_only)
        self.audio_format.setCurrentText(s.audio_format)
        self.video_format.setCurrentText(s.video_format)
        self.quality.setCurrentText(f"{s.quality}p")
        self.prefer_fps.setChecked(s.prefer_highest_fps)
        self.convert.setChecked(s.convert)
        self.set_bitrate.setChecked(s.set_bitrate)
        self.bitrate.setText(s.bitrate)
        self.audio_language.setText(s.audio_language)
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
        s.audio_only = self.mode_audio.isChecked()
        s.audio_format = self.audio_format.currentText()
        s.video_format = self.video_format.currentText()
        s.quality = self.quality.currentText().rstrip("p")
        s.prefer_highest_fps = self.prefer_fps.isChecked()
        s.convert = self.convert.isChecked()
        s.set_bitrate = self.set_bitrate.isChecked()
        s.bitrate = self.bitrate.text().strip() or "192"
        s.audio_language = self.audio_language.text().strip() or "default"
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

    @property
    def audio_only(self) -> bool:
        return self.mode_audio.isChecked()

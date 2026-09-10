"""Help: longer-form explanations, ported straight from the original app's
resource strings (so they're already translated in every locale)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...i18n import tr
from ..widgets.common import heading


class HelpPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)
        outer.addWidget(heading(tr("Help")))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(16)

        self._sections: list[tuple[QLabel, QLabel, str, str]] = []
        for title_key, body_key in (
            ("FileNamePatternTitle", "FileNamePattenExplanation"),
            ("Subscriptions", "SubscriptionsHelp"),
            ("LimitConverstions", "ConversionsLimitingExplanation"),
            ("ContactTheDeveloper", "ContactTheDeveloperHelp"),
            ("CreditsAndContributors", "CreditsAndContributors"),
        ):
            col.addWidget(self._section(title_key, body_key))

        col.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _section(self, title_key: str, body_key: str) -> QFrame:
        box = QFrame()
        box.setObjectName("Card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        title = heading(tr(title_key), level=2)
        text = QLabel(tr(body_key))
        text.setObjectName("Dim")
        text.setWordWrap(True)
        text.setTextInteractionFlags(text.textInteractionFlags().TextBrowserInteraction)
        text.setOpenExternalLinks(True)
        lay.addWidget(title)
        lay.addWidget(text)
        self._sections.append((title, text, title_key, body_key))
        return box

    def retranslate(self) -> None:
        for title, text, tk, bk in self._sections:
            title.setText(tr(tk))
            text.setText(tr(bk))

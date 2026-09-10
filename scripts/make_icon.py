"""Generate ytpdl/resources/app.png (and app.ico on Windows) — a rounded red
tile with a white download glyph. Run once; the result is committed.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication([])
S = 512
pix = QPixmap(S, S)
pix.fill(Qt.transparent)
p = QPainter(pix)
p.setRenderHint(QPainter.Antialiasing)

path = QPainterPath()
path.addRoundedRect(QRectF(24, 24, S - 48, S - 48), 96, 96)
p.fillPath(path, QBrush(QColor("#E51C23")))

p.setPen(Qt.NoPen)
p.setBrush(QColor("white"))
# arrow shaft
p.drawRoundedRect(QRectF(S / 2 - 34, 120, 68, 200), 20, 20)
# arrow head
head = QPainterPath()
head.moveTo(S / 2 - 110, 270)
head.lineTo(S / 2 + 110, 270)
head.lineTo(S / 2, 400)
head.closeSubpath()
p.drawPath(head)
# tray
p.drawRoundedRect(QRectF(120, 400, S - 240, 40), 16, 16)

p.end()

out = Path(__file__).resolve().parent.parent / "ytpdl" / "resources"
out.mkdir(parents=True, exist_ok=True)
pix.save(str(out / "app.png"))
for size in (16, 24, 32, 48, 64, 128, 256):
    pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(
        str(out / f"app-{size}.png")
    )
print("wrote", out / "app.png")

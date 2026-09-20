"""Generate ytpdl/resources/app.png, app.ico, and app.icns — a rounded red
tile with a white download glyph. Run once; the result is committed.

app.ico (Windows) and app.icns (macOS) are derived from app.png via Pillow,
which can write both formats on any platform — no need to run this on
Windows/macOS specifically to get their icon format.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPixmap
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

im = Image.open(out / "app.png")
im.save(out / "app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
im.save(out / "app.icns")

print("wrote", out / "app.png", out / "app.ico", out / "app.icns")

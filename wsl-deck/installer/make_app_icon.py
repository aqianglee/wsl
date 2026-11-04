"""把 App 內建的 QPainter 圖標輸出成 Windows .ico，供打包與安裝捷徑使用。

需在 Windows 平台執行（預設 qwindows 插件）；offscreen 插件缺少字型庫會把 W 畫成方框。
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication

from app.ui.app_icon import ICON_SIZES, app_pixmap

OUTPUT_PATH = Path(__file__).with_name("WSL Deck.ico")


def png_bytes(size: int) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    if not app_pixmap(size).save(buffer, "PNG"):
        raise RuntimeError(f"無法編碼 {size}px 圖標")
    data = bytes(buffer.data())
    buffer.close()
    return data


def write_ico(path: Path, frames: list[tuple[int, bytes]]) -> None:
    """以 PNG 壓縮幀寫出標準 ICO（Vista 以上支援）。"""
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = b""
    payload = b""
    offset = 6 + 16 * len(frames)
    for size, data in frames:
        dimension = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
        payload += data
    path.write_bytes(header + entries + payload)


def main() -> int:
    application = QGuiApplication(sys.argv)
    write_ico(OUTPUT_PATH, [(size, png_bytes(size)) for size in ICON_SIZES])
    print(f"已生成 {OUTPUT_PATH}（尺寸：{', '.join(map(str, ICON_SIZES))}）")
    del application
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

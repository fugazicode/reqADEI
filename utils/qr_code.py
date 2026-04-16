from __future__ import annotations

from io import BytesIO

import qrcode


def build_qr_png(data: str) -> bytes:
    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

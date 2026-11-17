"""Small, consistent vector icons drawn with Qt; no emoji font dependency."""

from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, QObject, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer


_REFERENCE_ICON_ASSET = Path(__file__).resolve().parent / "assets" / "Icon.svg"
_BRAND_ICON_ASSET = Path(__file__).resolve().parent / "assets" / "cachyos-softmgr.svg"
_REFERENCE_ICON_CROPS = {
    "update": (40.0, 54.5, 80.0),
    "refresh": (148.0, 56.5, 88.0),
    "trash": (262.0, 52.5, 90.0),
}


def _make_brand_icon(size: int) -> QIcon | None:
    if not _BRAND_ICON_ASSET.is_file():
        return None
    renderer = QSvgRenderer(str(_BRAND_ICON_ASSET))
    if not renderer.isValid():
        return None
    icon = QIcon()
    for pixel_size in sorted({16, 24, 32, 48, 64, 128, 256, size}):
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, pixel_size, pixel_size))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def _make_reference_icon(name: str, color: str, size: int) -> QIcon | None:
    crop = _REFERENCE_ICON_CROPS.get(name)
    if crop is None or not _REFERENCE_ICON_ASSET.is_file():
        return None
    try:
        svg = _REFERENCE_ICON_ASSET.read_text(encoding="utf-8").replace("#000000", color)
    except OSError:
        return None
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return None
    center_x, center_y, source_side = crop
    render_scale = 4
    margin = 16
    source_width, source_height = renderer.defaultSize().width(), renderer.defaultSize().height()
    full_pixmap = QPixmap(
        (source_width + margin * 2) * render_scale,
        (source_height + margin * 2) * render_scale,
    )
    full_pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(full_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(
        painter,
        QRectF(
            margin * render_scale,
            margin * render_scale,
            source_width * render_scale,
            source_height * render_scale,
        ),
    )
    painter.end()
    side = round(source_side * render_scale)
    left = round((center_x - source_side / 2 + margin) * render_scale)
    top = round((center_y - source_side / 2 + margin) * render_scale)
    crop_pixmap = full_pixmap.copy(left, top, side, side)
    return QIcon(crop_pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ))


def make_icon(name: str, color: str = "#0788C8", size: int = 24) -> QIcon:
    if name == "brand":
        brand_icon = _make_brand_icon(size)
        if brand_icon is not None:
            return brand_icon
    if name == "updates":
        name = "update"
    reference_icon = _make_reference_icon(name, color, size)
    if reference_icon is not None:
        return reference_icon
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setPen(QPen(QColor(color), max(1.6, size / 12), Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "brand":
        outer = QPainterPath()
        outer.moveTo(size * .5, size * .06)
        outer.lineTo(size * .94, size * .5)
        outer.lineTo(size * .5, size * .94)
        outer.lineTo(size * .06, size * .5)
        outer.closeSubpath()
        painter.drawPath(outer)
        inner = QPainterPath()
        inner.moveTo(size * .5, size * .25)
        inner.lineTo(size * .75, size * .5)
        inner.lineTo(size * .5, size * .75)
        inner.lineTo(size * .25, size * .5)
        inner.closeSubpath()
        painter.drawPath(inner)
        painter.drawLine(QPointF(size * .5, size * .38), QPointF(size * .5, size * .62))
        painter.drawLine(QPointF(size * .38, size * .5), QPointF(size * .62, size * .5))
    elif name == "search":
        painter.drawEllipse(QRectF(size * .13, size * .12, size * .56, size * .56))
        painter.drawLine(QPointF(size * .59, size * .59), QPointF(size * .88, size * .88))
    elif name == "chevron-down":
        path = QPainterPath(QPointF(size * .27, size * .39))
        path.lineTo(size * .5, size * .62)
        path.lineTo(size * .73, size * .39)
        painter.drawPath(path)
    elif name == "refresh":
        painter.drawArc(QRectF(size * .18, size * .18, size * .64, size * .64), 35 * 16, 285 * 16)
        head = QPainterPath(QPointF(size * .67, size * .12))
        head.lineTo(size * .87, size * .14)
        head.lineTo(size * .83, size * .34)
        painter.drawPath(head)
    elif name == "update":
        painter.drawLine(QPointF(size * .5, size * .81), QPointF(size * .5, size * .25))
        path = QPainterPath(QPointF(size * .25, size * .48))
        path.lineTo(size * .5, size * .22)
        path.lineTo(size * .75, size * .48)
        painter.drawPath(path)
        painter.drawLine(QPointF(size * .23, size * .83), QPointF(size * .77, size * .83))
    elif name == "trash":
        painter.drawLine(QPointF(size * .19, size * .28), QPointF(size * .81, size * .28))
        painter.drawLine(QPointF(size * .38, size * .2), QPointF(size * .62, size * .2))
        painter.drawLine(QPointF(size * .3, size * .34), QPointF(size * .35, size * .83))
        painter.drawLine(QPointF(size * .7, size * .34), QPointF(size * .65, size * .83))
        painter.drawLine(QPointF(size * .35, size * .83), QPointF(size * .65, size * .83))
        painter.drawLine(QPointF(size * .45, size * .42), QPointF(size * .46, size * .72))
        painter.drawLine(QPointF(size * .55, size * .42), QPointF(size * .54, size * .72))
    elif name == "sun":
        painter.drawEllipse(QRectF(size * .34, size * .34, size * .32, size * .32))
        for angle in range(0, 360, 45):
            a = math.radians(angle)
            painter.drawLine(
                QPointF(size * (.5 + .27 * math.cos(a)), size * (.5 + .27 * math.sin(a))),
                QPointF(size * (.5 + .39 * math.cos(a)), size * (.5 + .39 * math.sin(a))),
            )
    elif name == "moon":
        path = QPainterPath(QPointF(size * .68, size * .13))
        path.cubicTo(size * .33, size * .12, size * .16, size * .36, size * .2, size * .57)
        path.cubicTo(size * .25, size * .84, size * .58, size * .93, size * .8, size * .73)
        path.cubicTo(size * .59, size * .79, size * .43, size * .62, size * .43, size * .43)
        path.cubicTo(size * .43, size * .28, size * .53, size * .18, size * .68, size * .13)
        painter.drawPath(path)
    elif name == "package":
        path = QPainterPath(QPointF(size * .5, size * .12))
        path.lineTo(size * .84, size * .3)
        path.lineTo(size * .84, size * .7)
        path.lineTo(size * .5, size * .88)
        path.lineTo(size * .16, size * .7)
        path.lineTo(size * .16, size * .3)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(size * .16, size * .3), QPointF(size * .5, size * .49))
        painter.drawLine(QPointF(size * .84, size * .3), QPointF(size * .5, size * .49))
        painter.drawLine(QPointF(size * .5, size * .49), QPointF(size * .5, size * .88))
    elif name == "updates":
        for y in (.27, .5, .73):
            painter.drawLine(QPointF(size * .3, size * y), QPointF(size * .82, size * y))
        painter.drawEllipse(QPointF(size * .16, size * .27), size * .045, size * .045)
        painter.drawEllipse(QPointF(size * .16, size * .5), size * .045, size * .045)
        painter.drawEllipse(QPointF(size * .16, size * .73), size * .045, size * .045)
    elif name == "storage":
        painter.drawRoundedRect(QRectF(size * .12, size * .2, size * .76, size * .6), size * .1, size * .1)
        painter.drawLine(QPointF(size * .18, size * .57), QPointF(size * .82, size * .57))
        painter.drawEllipse(QPointF(size * .7, size * .72), size * .035, size * .035)
        painter.drawEllipse(QPointF(size * .81, size * .72), size * .035, size * .035)
    elif name == "aur":
        painter.drawLine(QPointF(size * .28, size * .72), QPointF(size * .5, size * .3))
        painter.drawLine(QPointF(size * .5, size * .3), QPointF(size * .75, size * .68))
        painter.drawLine(QPointF(size * .28, size * .72), QPointF(size * .75, size * .68))
        for x, y in ((.28, .72), (.5, .3), (.75, .68)):
            painter.drawEllipse(QPointF(size * x, size * y), size * .09, size * .09)
    elif name == "flatpak":
        painter.drawRoundedRect(QRectF(size * .12, size * .16, size * .76, size * .68), size * .08, size * .08)
        painter.drawLine(QPointF(size * .14, size * .36), QPointF(size * .86, size * .36))
        for x in (.25, .38, .51):
            painter.drawEllipse(QPointF(size * x, size * .26), size * .025, size * .025)
        painter.drawRoundedRect(QRectF(size * .34, size * .48, size * .32, size * .22), size * .035, size * .035)

    painter.end()
    return QIcon(pixmap)


class _ButtonIconStateFilter(QObject):
    def __init__(self, button, name: str, colors: tuple[str, str, str], size: int):
        super().__init__(button)
        self.button = button
        self.name = name
        self.colors = colors
        self.size = size

    def update(self, name: str, colors: tuple[str, str, str], size: int) -> None:
        self.name = name
        self.colors = colors
        self.size = size
        self.button.setIconSize(QSize(size, size))
        self.apply()

    def apply(self) -> None:
        normal, active, disabled = self.colors
        color = disabled if not self.button.isEnabled() else active if self.button.underMouse() else normal
        self.button.setIcon(make_icon(self.name, color, self.size))

    def eventFilter(self, watched, event) -> bool:
        if watched is self.button and event.type() in {
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.EnabledChange,
            QEvent.Type.Show,
        }:
            self.apply()
        return False


def set_stateful_button_icon(
    button,
    name: str,
    normal_color: str,
    active_color: str,
    disabled_color: str,
    size: int = 20,
) -> None:
    """Keep a button icon in sync with hover and enabled states across Qt themes."""
    colors = (normal_color, active_color, disabled_color)
    state_filter = getattr(button, "_softmgr_icon_state_filter", None)
    if state_filter is None:
        state_filter = _ButtonIconStateFilter(button, name, colors, size)
        button._softmgr_icon_state_filter = state_filter
        button.installEventFilter(state_filter)
    state_filter.update(name, colors, size)

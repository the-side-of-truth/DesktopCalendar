# -*- coding: utf-8 -*-
"""X11 输入裁剪：让窗口只在指定矩形内接收鼠标，其余区域鼠标事件穿透到桌面/其他窗口。

原理：X Shape 扩展的 ShapeInput 区域由 X 服务器做指针命中测试。直接裁剪客户区窗口会让
事件整体失效（KWin 会给客户区套两层 frame），因此这里只裁剪 WM 生成的祖先 frame 窗口，
客户区保持默认（全窗口），实测在 UKUI/KWin 下裁剪区内仍可正常收到鼠标事件。
"""
import ctypes
import os
import sys
import threading
import time
from ctypes import (POINTER, Structure, byref, c_char_p, c_int, c_short,
                    c_ubyte, c_uint, c_ulong, c_void_p, cast)

from PyQt5.QtCore import QObject, QRect, pyqtSignal


class _XRectangle(Structure):
    _fields_ = [("x", c_short), ("y", c_short),
                ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]


class ClickThroughRegion:
    """把窗口的鼠标可交互区域限制为若干矩形（窗口内坐标）。

    非 X11 环境自动降级为空实现，窗口行为与原来一致。
    """

    _SHAPE_INPUT = 2
    _SHAPE_SET = 0
    _UNSORTED = 0

    def __init__(self, widget):
        self.widget = widget
        self.enabled = False
        self._dpy = None
        self._x11 = None
        self._xext = None
        self._root = 0
        self._sig = None
        if not (sys.platform.startswith("linux") and os.environ.get("DISPLAY")):
            return
        try:
            self._x11 = ctypes.CDLL("libX11.so.6")
            self._xext = ctypes.CDLL("libXext.so.6")
            self._bind()
            self._dpy = self._x11.XOpenDisplay(None)
            if not self._dpy:
                return
            self._root = self._x11.XDefaultRootWindow(self._dpy)
            self.enabled = True
        except (OSError, AttributeError):
            self.enabled = False

    def _bind(self):
        x11, xext = self._x11, self._xext
        x11.XOpenDisplay.restype = c_void_p
        x11.XOpenDisplay.argtypes = [c_char_p]
        x11.XDefaultRootWindow.restype = c_ulong
        x11.XDefaultRootWindow.argtypes = [c_void_p]
        x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong),
                                   POINTER(c_ulong), POINTER(POINTER(c_ulong)),
                                   POINTER(c_uint)]
        x11.XFree.argtypes = [c_void_p]
        x11.XSync.argtypes = [c_void_p, c_int]
        x11.XTranslateCoordinates.argtypes = [
            c_void_p, c_ulong, c_ulong, c_int, c_int,
            POINTER(c_int), POINTER(c_int), POINTER(c_ulong)]
        xext.XShapeCombineRectangles.argtypes = [
            c_void_p, c_ulong, c_int, c_int, c_int,
            POINTER(_XRectangle), c_int, c_int, c_int]

    # ---------- 内部 ----------
    def _frames(self):
        """返回 (客户区窗口, [WM 祖先 frame ...])，由内到外"""
        win = int(self.widget.winId())
        frames = []
        root, parent = c_ulong(), c_ulong()
        children = POINTER(c_ulong)()
        count = c_uint()
        cur = win
        for _ in range(8):
            if not self._x11.XQueryTree(self._dpy, cur, byref(root), byref(parent),
                                        byref(children), byref(count)):
                break
            if children:
                self._x11.XFree(cast(children, c_void_p))
            nxt = parent.value
            if nxt in (0, self._root):
                break
            frames.append(nxt)
            cur = nxt
        return win, frames

    def _offset_in(self, frame, win):
        """客户区原点在 frame 内的偏移（frame 可能带边框/阴影区域）"""
        dx, dy, child = c_int(), c_int(), c_ulong()
        if self._x11.XTranslateCoordinates(self._dpy, win, frame, 0, 0,
                                           byref(dx), byref(dy), byref(child)):
            return dx.value, dy.value
        return 0, 0

    def _apply_rects(self, frames, win, rects):
        for frame in frames:
            ox, oy = self._offset_in(frame, win)
            arr = (_XRectangle * len(rects))(*[
                _XRectangle(r.x() + ox, r.y() + oy, r.width(), r.height())
                for r in rects])
            self._xext.XShapeCombineRectangles(
                self._dpy, frame, self._SHAPE_INPUT, 0, 0, arr, len(rects),
                self._SHAPE_SET, self._UNSORTED)
        self._x11.XSync(self._dpy, 0)

    # ---------- 对外 ----------
    def invalidate(self):
        self._sig = None

    def apply(self, rects):
        """只让 rects（窗口内坐标）接收鼠标；rects 为空时退回整窗可交互"""
        if not self.enabled or not self.widget.isVisible():
            return
        win, frames = self._frames()
        if not frames:
            return
        area = self.widget.rect()
        clipped = []
        for r in rects:
            inter = r.intersected(area)
            if inter.width() > 0 and inter.height() > 0:
                clipped.append(QRect(inter))
        if not clipped:
            clipped = [QRect(0, 0, max(1, area.width()), max(1, area.height()))]
        sig = (win, tuple(frames), tuple((r.x(), r.y(), r.width(), r.height())
                                         for r in clipped))
        if sig == self._sig:
            return
        self._apply_rects(frames, win, clipped)
        self._sig = sig

    def release(self):
        """恢复整窗可交互（拖动/缩放时使用，保证手感连续）"""
        if not self.enabled or not self.widget.isVisible():
            return
        win, frames = self._frames()
        if not frames:
            return
        area = self.widget.rect()
        self._apply_rects(frames, win,
                          [QRect(0, 0, max(1, area.width()), max(1, area.height()))])
        self._sig = None

    def occluded(self, win):
        """指针下的顶层窗口 win 是否位于本窗口之上（即该点被其他应用窗口遮挡）。

        本窗口开启了 WindowStaysOnBottom，桌面/图标窗口在它之下，不算遮挡；
        普通应用窗口在它之上，才算遮挡。
        """
        if not self.enabled or not win:
            return False
        # 本窗口在根窗口下的顶层祖先（WM frame）
        top = int(self.widget.winId())
        for _ in range(8):
            root, parent = c_ulong(), c_ulong()
            children = POINTER(c_ulong)()
            count = c_uint()
            if not self._x11.XQueryTree(self._dpy, top, byref(root),
                                        byref(parent), byref(children),
                                        byref(count)):
                return False
            if children:
                self._x11.XFree(cast(children, c_void_p))
            nxt = parent.value
            if nxt in (0, self._root):
                break
            top = nxt
        # 根窗口子窗口按层叠顺序（底→顶）返回，win 的序号更大说明它在本窗口之上
        root, parent = c_ulong(), c_ulong()
        children = POINTER(c_ulong)()
        count = c_uint()
        if not self._x11.XQueryTree(self._dpy, self._root, byref(root),
                                    byref(parent), byref(children), byref(count)):
            return False
        order = [children[i] for i in range(count.value)]
        if children:
            self._x11.XFree(cast(children, c_void_p))
        try:
            return order.index(win) > order.index(top)
        except ValueError:
            return False


class _XIEventMask(Structure):
    _fields_ = [("deviceid", c_int), ("mask_len", c_int),
                ("mask", POINTER(c_ubyte))]


class _XGenericEventCookie(Structure):
    _fields_ = [("type", c_int), ("serial", c_ulong), ("send_event", c_int),
                ("display", c_void_p), ("extension", c_int), ("evtype", c_int),
                ("cookie", c_uint), ("data", c_void_p)]


class _XIRawEvent(Structure):
    _fields_ = [("type", c_int), ("serial", c_ulong), ("send_event", c_int),
                ("display", c_void_p), ("extension", c_int), ("evtype", c_int),
                ("time", c_ulong), ("deviceid", c_int), ("sourceid", c_int),
                ("detail", c_int), ("flags", c_int), ("valuators", c_void_p),
                ("raw_values", c_void_p), ("num_valuators", c_int)]


class GlobalDoubleClickWatcher(QObject):
    """全局双击监听（X11 XI2 原始按键事件）：不抢占、不阻塞任何鼠标事件。

    日单元格已从窗口输入区域移除（鼠标全部交给桌面/图标），双击只能靠全局监听识别。
    订阅 XI_RawButtonPress 由 X 服务器推送，即使主线程繁忙也不会漏掉按下。
    """
    doubleClicked = pyqtSignal(int, int)      # 屏幕坐标

    _GENERIC_EVENT = 35
    _RAW_PRESS = 15
    _RAW_RELEASE = 16
    _ALL_MASTER = 1          # XIAllMasterDevices
    _DBL_INTERVAL = 0.35     # 两次按下最大间隔（秒）
    _DBL_DIST = 8            # 两次按下最大位移（像素）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = False
        self._x11 = None
        self._xi = None
        self._dpy = None         # 监听线程专用连接（会阻塞在 XNextEvent）
        self._dpy_q = None       # 主线程查询专用连接
        self._root = 0
        self._thread = None
        self._stop = threading.Event()
        self._ptr = None         # 最近一次左键按下时的 (x, y, 指针下窗口, 是否按下)
        self._last_press = None  # (时刻, x, y, 第一次按下时的快照)
        self._dbl_snapshot = None
        if not (sys.platform.startswith("linux") and os.environ.get("DISPLAY")):
            return
        try:
            x11 = ctypes.CDLL("libX11.so.6")
            xi = ctypes.CDLL("libXi.so.6")
            x11.XOpenDisplay.restype = c_void_p
            x11.XOpenDisplay.argtypes = [c_char_p]
            x11.XDefaultRootWindow.restype = c_ulong
            x11.XDefaultRootWindow.argtypes = [c_void_p]
            x11.XNextEvent.argtypes = [c_void_p, c_void_p]
            x11.XSync.argtypes = [c_void_p, c_int]
            x11.XQueryPointer.argtypes = [
                c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong),
                POINTER(c_int), POINTER(c_int), POINTER(c_int), POINTER(c_int),
                POINTER(c_uint)]
            x11.XGetEventData.argtypes = [c_void_p, c_void_p]
            x11.XFreeEventData.argtypes = [c_void_p, c_void_p]
            x11.XGetInputFocus.argtypes = [c_void_p, POINTER(c_ulong),
                                           POINTER(c_int)]
            x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong),
                                       POINTER(c_ulong), POINTER(POINTER(c_ulong)),
                                       POINTER(c_uint)]
            x11.XFree.argtypes = [c_void_p]
            xi.XIQueryVersion.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
            xi.XISelectEvents.argtypes = [c_void_p, c_ulong, c_void_p, c_int]
            self._x11 = x11
            self._xi = xi
            self._dpy = x11.XOpenDisplay(None)
            self._dpy_q = x11.XOpenDisplay(None)
            if self._dpy and self._dpy_q:
                self._root = x11.XDefaultRootWindow(self._dpy)
                self.enabled = self._subscribe()
        except (OSError, AttributeError):
            self.enabled = False

    def _subscribe(self):
        """在监听连接上订阅原始按键事件（按下/抬起，所有主设备）"""
        major, minor = c_int(2), c_int(2)
        if self._xi.XIQueryVersion(self._dpy, byref(major), byref(minor)) != 0:
            return False
        bits = (c_ubyte * 4)()
        for evtype in (self._RAW_PRESS, self._RAW_RELEASE):
            bits[evtype // 8] |= 1 << (evtype % 8)
        mask = _XIEventMask(self._ALL_MASTER, 4, cast(bits, POINTER(c_ubyte)))
        if self._xi.XISelectEvents(self._dpy, self._root, byref(mask), 1) != 0:
            return False
        self._x11.XSync(self._dpy, 0)
        return True

    def start(self):
        if not self.enabled or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="dblclick-watch",
                                        daemon=True)
        self._thread.start()

    # ---------- 查询 ----------
    def pointer(self):
        """返回最近一次左键按下时的 (x, y, 该点最上层窗口, 是否仍按下)"""
        return self._ptr

    def focus_window(self):
        if not self.enabled:
            return 0
        win, revert = c_ulong(), c_int()
        self._x11.XGetInputFocus(self._dpy_q, byref(win), byref(revert))
        return win.value

    def root_children(self):
        """根窗口子窗口集合：新开/关闭应用窗口时会变化"""
        if not self.enabled:
            return ()
        root, parent = c_ulong(), c_ulong()
        children = POINTER(c_ulong)()
        count = c_uint()
        if not self._x11.XQueryTree(self._dpy_q, self._root, byref(root),
                                    byref(parent), byref(children), byref(count)):
            return ()
        ids = tuple(children[i] for i in range(count.value))
        if children:
            self._x11.XFree(cast(children, c_void_p))
        return ids

    def first_press_snapshot(self):
        """双击中第一次按下时的 (焦点窗口, 根子窗口) 快照"""
        return self._dbl_snapshot

    # ---------- 事件循环（独立线程） ----------
    def _query_pointer(self):
        root_ret, child = c_ulong(), c_ulong()
        rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
        mask = c_uint()
        if not self._x11.XQueryPointer(self._dpy, self._root, byref(root_ret),
                                       byref(child), byref(rx), byref(ry),
                                       byref(wx), byref(wy), byref(mask)):
            return None
        return rx.value, ry.value, child.value, bool(mask.value & (1 << 8))

    def _snapshot(self):
        """当前 (焦点窗口, 根子窗口)：图标/桌面对双击有反应时两者会变化"""
        win, revert = c_ulong(), c_int()
        self._x11.XGetInputFocus(self._dpy, byref(win), byref(revert))
        root, parent = c_ulong(), c_ulong()
        children = POINTER(c_ulong)()
        count = c_uint()
        ids = ()
        if self._x11.XQueryTree(self._dpy, self._root, byref(root), byref(parent),
                                byref(children), byref(count)):
            ids = tuple(children[i] for i in range(count.value))
            if children:
                self._x11.XFree(cast(children, c_void_p))
        return win.value, ids

    def _loop(self):
        buf = (_XGenericEventCookie * 4)()      # 224 字节缓冲（XEvent 为 192 字节）
        ev = cast(buf, POINTER(_XGenericEventCookie))
        while not self._stop.is_set():
            self._x11.XNextEvent(self._dpy, buf)
            if ev.contents.type != self._GENERIC_EVENT:
                continue
            if not self._x11.XGetEventData(self._dpy, ev):
                continue
            try:
                if not ev.contents.data:
                    continue
                raw = _XIRawEvent.from_address(ev.contents.data)
                evtype, detail = raw.evtype, raw.detail
                t_ms = int(raw.time)
            finally:
                self._x11.XFreeEventData(self._dpy, ev)
            if evtype != self._RAW_PRESS or detail != 1:
                continue            # 只关心左键按下
            st = self._query_pointer()
            if st is None:
                continue
            self._ptr = st
            x, y = st[0], st[1]
            snap = self._snapshot()
            last = self._last_press
            self._last_press = (t_ms, x, y, snap)
            dt = ((t_ms - last[0]) & 0xFFFFFFFF) if last else None
            # 用服务器时间戳判断双击：桌面卡顿导致的处理延迟不会误判
            if (last and dt <= self._DBL_INTERVAL * 1000
                    and abs(x - last[1]) <= self._DBL_DIST
                    and abs(y - last[2]) <= self._DBL_DIST):
                self._last_press = None       # 三连击不重复触发
                self._dbl_snapshot = last[3]  # 第一次按下（图标尚未反应）时的状态
                self.doubleClicked.emit(x, y)

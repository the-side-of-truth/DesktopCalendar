# -*- coding: utf-8 -*-
"""桌面日历入口：单实例运行，重复启动时显示已隐藏的主窗口"""
import os
import sys

from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import QApplication

SERVER_NAME = "DesktopCalendarApp"


def main():
    QApplication.setApplicationName("DesktopCalendar")
    QApplication.setOrganizationName("DesktopCalendar")
    app = QApplication(sys.argv)
    # 隐藏主窗口不等于退出程序（提醒等后台功能继续运行）
    app.setQuitOnLastWindowClosed(False)

    # 单实例：已运行则通知其显示并退出
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return 0

    from app.core.settings import Settings
    from app.core.database import Database
    from app.ui.main_window import MainWindow

    settings = Settings()
    db = Database(os.path.join(settings.dir, "calendar.db"))
    win = MainWindow(settings, db)
    win.show()

    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)

    def _on_conn():
        conn = server.nextPendingConnection()
        if conn:
            conn.readAll()
            conn.disconnectFromServer()
        win.showNormal()
        win.raise_()
        win.activateWindow()

    server.newConnection.connect(_on_conn)
    code = app.exec_()
    db.close()
    QLocalServer.removeServer(SERVER_NAME)
    return code


if __name__ == "__main__":
    sys.exit(main())

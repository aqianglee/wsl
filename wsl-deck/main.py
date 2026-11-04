"""WSL Deck 入口（含 --silent 與打包後的 --admin-job）。"""

from __future__ import annotations

import logging
import sys

from app.paths import app_dir


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["--admin-job"] and len(argv) == 3:
        from app.admin import main as admin_main
        return admin_main(argv[1:])

    silent = "--silent" in argv
    argv = [arg for arg in argv if arg != "--silent"]

    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.config import Config, ConfigError
    from app.logbus import setup_logging
    from app.proxy import apply_runtime, parse_config
    from app.single_instance import SingleInstance
    from app.ui.main_window import MainWindow
    from app.ui.theme import apply_theme
    from app.workspace import ensure_workspace

    app = QApplication([sys.argv[0], *argv])
    app.setApplicationName("WSL Deck")
    app.setOrganizationName("WSL Deck")

    instance = SingleInstance("WSL Deck")
    if not instance.acquire():
        if not silent:
            instance.activate_existing()
        return 0

    try:
        config = Config(app_dir() / "config.json")
    except ConfigError as exc:
        QMessageBox.critical(None, "配置錯誤", str(exc))
        return 1

    setup_logging(config.resolve_path(config.data["log_file"]))
    apply_runtime(parse_config(config.get("proxy")))
    apply_theme(app, str(config.get("theme", "system")))
    logger = logging.getLogger(__name__)
    logger.info("WSL Deck 啟動，配置：%s", config.path)
    try:
        ensure_workspace(config.workspace())
    except OSError as exc:
        logger.warning("建立工作目錄骨架失敗：%s", exc)

    window = MainWindow(config)
    instance.activated.connect(window.show_window)
    if not (silent and window.tray_available):
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

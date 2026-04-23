"""Entry point: bootstrap layout, then desktop login → main window."""

import sys

from PyQt5.QtWidgets import QApplication

from app.bootstrap import bootstrap
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
from ui.theme import apply_theme


def main() -> int:
    bootstrap()
    app = QApplication(sys.argv)
    apply_theme(app)
    main_win = MainWindow()
    main_win.hide()

    def run_login_dialog() -> bool:
        login = LoginWindow()

        def on_login_ok(username: str) -> None:
            main_win.set_current_user(username)
            main_win.show()

        login.login_succeeded.connect(on_login_ok)
        return login.exec_() == LoginWindow.Accepted

    def on_logout_requested() -> None:
        main_win.hide()
        main_win.clear_current_user()
        if not run_login_dialog():
            app.quit()

    main_win.logout_requested.connect(on_logout_requested)
    if not run_login_dialog():
        return 0
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

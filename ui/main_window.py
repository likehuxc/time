"""Primary application window with tab navigation for feature pages."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QWidget

from services.record_service import claim_legacy_prediction_records
from ui.pages.data_page import DataPage
from ui.pages.forecast_page import ForecastPage
from ui.pages.records_page import RecordsPage
from ui.pages.user_page import UserPage


class MainWindow(QMainWindow):
    """Desktop shell: top tabs and page widgets."""

    logout_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Household Load Forecast System")
        self.resize(960, 600)
        self.setObjectName("mainWindowRoot")

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("mainTabs")
        self.setCentralWidget(self._tabs)

        self._data = DataPage(self)
        self._forecast = ForecastPage(self)
        self._records = RecordsPage(self)
        self._user = UserPage(self)

        self._tabs.addTab(self._data, "数据工作台")
        self._tabs.addTab(self._forecast, "预测工作台")
        self._tabs.addTab(self._records, "历史记录")
        self._tabs.addTab(self._user, "用户")

        self._data.prepared_hourly_ready.connect(self._on_data_hourly_ready)
        self._forecast.prediction_records_changed.connect(self._records.refresh)
        self._user.logout_requested.connect(self.logout_requested.emit)
        self.statusBar().setObjectName("mainStatusBar")
        self.statusBar().showMessage("就绪。请使用顶部页签切换各工作台。")

    def set_current_user(self, username: str) -> None:
        claim_legacy_prediction_records(username)
        self._forecast.set_current_user(username)
        self._records.set_current_user(username)
        self._user.set_current_user(username)
        self.statusBar().showMessage(f"已登录用户：{username}")

    def clear_current_user(self) -> None:
        self._data.reset_session_state()
        self._forecast.reset_session_state()
        self._records.clear_current_user()
        self._tabs.setCurrentWidget(self._data)
        self._user.clear_current_user()
        self.statusBar().showMessage("已退出登录。")

    def _on_data_hourly_ready(self, series: object) -> None:
        self._forecast.load_prepared_series(series)
        self.statusBar().showMessage(
            "已将小时级 WHE 同步至预测工作台；当前仍在数据工作台，可切换到“预测工作台”查看。"
        )

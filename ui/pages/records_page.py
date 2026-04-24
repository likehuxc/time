"""历史预测记录列表页。"""

from __future__ import annotations

import json

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.record_service import (
    clear_prediction_records,
    delete_prediction_records,
    list_prediction_records,
)


class RecordsPage(QWidget):
    """展示当前用户的历史预测记录。"""

    _OUTPUT_PATH_COLUMN = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_username: str | None = None
        self._row_record_ids: list[int] = []

        page_title = QLabel("历史预测记录")
        page_title.setObjectName("pageTitle")

        intro = QLabel("这里会自动展示当前账号最近生成的预测记录和导出路径。")
        intro.setWordWrap(True)
        intro.setObjectName("pageIntro")

        self._empty_hint = QLabel("暂无历史预测记录，完成一次预测后会自动出现在这里。")
        self._empty_hint.setObjectName("summaryCard")
        self._empty_hint.setWordWrap(True)

        refresh = QPushButton("刷新")
        refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self.refresh)

        delete_selected = QPushButton("删除选中")
        delete_selected.setObjectName("dangerButton")
        delete_selected.clicked.connect(self._delete_selected)

        clear_all = QPushButton("一键清空")
        clear_all.setObjectName("dangerButton")
        clear_all.clicked.connect(self._clear_all)

        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        toolbar.addWidget(delete_selected)
        toolbar.addWidget(clear_all)
        toolbar.addWidget(refresh)

        self._table = QTableWidget(0, 6, self)
        self._table.setObjectName("recordsTable")
        self._table.setHorizontalHeaderLabels(
            ["记录ID", "创建时间", "户型", "模型名称", "预测周期", "输出路径"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.verticalHeader().hide()
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_table_context_menu)

        layout = QVBoxLayout(self)
        layout.addWidget(page_title)
        layout.addWidget(intro)
        layout.addLayout(toolbar)
        layout.addWidget(self._empty_hint)
        layout.addWidget(self._table, stretch=1)

        self.refresh()

    def set_current_user(self, username: str) -> None:
        self._current_username = username
        self.refresh()

    def clear_current_user(self) -> None:
        self._current_username = None
        self.refresh()

    def refresh(self) -> None:
        if not self._current_username:
            self._set_rows([])
            return
        rows = list_prediction_records(username=self._current_username, limit=200)
        rows = sorted(rows, key=lambda row: int(row.get("id", 0) or 0))
        self._set_rows(rows)

    def _set_rows(self, rows: list[dict[str, object]]) -> None:
        self._row_record_ids = []
        self._table.setRowCount(len(rows))
        self._empty_hint.setVisible(len(rows) == 0)
        for i, row in enumerate(rows):
            metrics = self._parse_metrics(row.get("metrics_json", ""))
            self._row_record_ids.append(int(row.get("id", 0) or 0))
            self._table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._table.setItem(i, 1, QTableWidgetItem(str(row.get("created_at", ""))))
            self._table.setItem(
                i,
                2,
                QTableWidgetItem(
                    str(
                        metrics.get("household_display")
                        or self._display_household(row.get("model_id", ""))
                    )
                ),
            )
            self._table.setItem(
                i,
                3,
                QTableWidgetItem(
                    str(
                        metrics.get("display_model")
                        or self._display_model(row.get("model_id", ""))
                    )
                ),
            )
            self._table.setItem(
                i,
                4,
                QTableWidgetItem(
                    str(
                        metrics.get("display_horizon")
                        or self._display_horizon(row.get("horizon_key", ""))
                    )
                ),
            )
            self._table.setItem(i, 5, QTableWidgetItem(str(row.get("output_path", ""))))

    def _delete_selected(self) -> None:
        if not self._current_username:
            return
        record_ids: list[int] = []
        for index in self._table.selectionModel().selectedRows():
            if 0 <= index.row() < len(self._row_record_ids):
                record_ids.append(self._row_record_ids[index.row()])
        delete_prediction_records(record_ids, username=self._current_username)
        self.refresh()

    def _clear_all(self) -> None:
        if not self._current_username:
            return
        clear_prediction_records(username=self._current_username)
        self.refresh()

    def _show_table_context_menu(self, pos: QPoint) -> None:
        item = self._table.itemAt(pos)
        if item is None or item.column() != self._OUTPUT_PATH_COLUMN:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("复制路径")
        chosen_action = menu.exec_(self._table.viewport().mapToGlobal(pos))
        if chosen_action == copy_action:
            self._copy_output_path_text(item.text())

    @staticmethod
    def _copy_output_path_text(path_text: object) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(path_text))

    @staticmethod
    def _parse_metrics(raw: object) -> dict[str, object]:
        if not isinstance(raw, str) or not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    @staticmethod
    def _display_household(model_id: object) -> str:
        model_text = str(model_id)
        if "ampds" in model_text:
            return "单户"
        if "londonb0" in model_text:
            return "多户"
        return model_text

    @staticmethod
    def _display_model(model_id: object) -> str:
        model_text = str(model_id)
        if "dc_itransformer" in model_text:
            return "DC-iTransformer"
        if "patchtst" in model_text:
            return "PatchTST"
        if "timexer" in model_text:
            return "TimeXer"
        return model_text

    @staticmethod
    def _display_horizon(horizon_key: object) -> str:
        horizon_text = str(horizon_key)
        if horizon_text == "1d":
            return "1天"
        if horizon_text == "7d":
            return "7天"
        return horizon_text

"""数据工作台：CSV 选择与预处理。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Union

import matplotlib

matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "SimSun",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.paths import RESOURCES_DIR
from inference_engine.resampler import MISSING_TIME_CONTEXT_ERROR
from services.data_service import load_and_prepare_csv

_DISPLAY_COLUMNS = ("date", "WHE", "OT", "Wind", "RH")
_TEMPLATE_CSV = RESOURCES_DIR / "templates" / "household_load_template.csv"


class DataPage(QWidget):
    """数据导入：选择 CSV，调用 ``load_and_prepare_csv``，成功则发出小时级 WHE 序列。"""

    prepared_hourly_ready = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        title = QLabel("数据工作台")
        title.setObjectName("dataPageTitle")

        hint = QLabel(
            "选择含 <b>WHE</b> 列的 CSV（可选 <b>date</b>、<b>OT</b>、<b>Wind</b>、<b>RH</b>），"
            "系统将规范为按小时对齐并传递到预测页。"
            "<br/>若无 <b>date</b> 列，需在后续版本填写起始时间与频率；当前请改用带日期列的模板。"
        )
        hint.setWordWrap(True)

        self._pick_btn = QPushButton("选择 CSV 文件…", self)
        self._pick_btn.clicked.connect(self._on_pick_file)

        self._status = QLabel("未选择文件。")
        self._status.setWordWrap(True)

        self._btn_download = QPushButton("下载数据集模板", self)
        self._btn_download.setObjectName("dataPageBtnDownloadTemplate")
        self._btn_download.clicked.connect(self._on_download_template)

        self._btn_show_table = QPushButton("数据展示", self)
        self._btn_show_table.setObjectName("dataPageBtnShowTable")
        self._btn_show_table.clicked.connect(self._show_table_view)

        self._btn_show_chart = QPushButton("数据可视化", self)
        self._btn_show_chart.setObjectName("dataPageBtnShowChart")
        self._btn_show_chart.clicked.connect(self._show_chart_view)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._btn_download)
        toolbar.addWidget(self._btn_show_table)
        toolbar.addWidget(self._btn_show_chart)
        toolbar.addStretch(1)

        self._table = QTableWidget(0, 0, self)
        self._table.setObjectName("dataPageTable")
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self._figure = Figure(figsize=(8.0, 4.0), layout="tight")
        self._chart_canvas = FigureCanvasQTAgg(self._figure)
        self._chart_canvas.setObjectName("dataPageChartCanvas")
        self._chart_canvas.setMinimumHeight(220)
        self._ax = self._figure.add_subplot(111)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName("dataPageViewStack")
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._chart_canvas)

        stats_title = QLabel("WHE 统计（小时级）")
        stats_title.setObjectName("dataPageStatsTitle")

        self._stat_mean = QLabel("均值：—")
        self._stat_mean.setObjectName("dataPageStatMean")
        self._stat_max = QLabel("最大值：—")
        self._stat_max.setObjectName("dataPageStatMax")
        self._stat_min = QLabel("最小值：—")
        self._stat_min.setObjectName("dataPageStatMin")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._pick_btn)
        layout.addWidget(self._status)
        layout.addLayout(toolbar)
        layout.addWidget(self._stack, stretch=1)
        layout.addWidget(stats_title)
        layout.addWidget(self._stat_mean)
        layout.addWidget(self._stat_max)
        layout.addWidget(self._stat_min)

        self._show_table_view()

    def _show_table_view(self) -> None:
        self._stack.setCurrentIndex(0)

    def _show_chart_view(self) -> None:
        self._stack.setCurrentIndex(1)

    def _on_download_template(self) -> None:
        if not _TEMPLATE_CSV.is_file():
            QMessageBox.warning(
                self,
                "模板缺失",
                f"未找到模板文件：{_TEMPLATE_CSV}",
            )
            return
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "保存数据集模板",
            str(_TEMPLATE_CSV.name),
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            shutil.copyfile(_TEMPLATE_CSV, path)
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", f"无法写入文件：{exc}")

    def _on_pick_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "选择 CSV 文件",
            "",
            "CSV 文件 (*.csv);;所有文件 (*.*)",
        )
        if path:
            self.process_csv_path(path)

    def _visible_display_columns(self, frame: pd.DataFrame) -> list[str]:
        return [c for c in _DISPLAY_COLUMNS if c in frame.columns]

    def _format_cell_text(self, col: str, val: object) -> str:
        if col == "date":
            if pd.isna(val):
                return ""
            ts = pd.Timestamp(val)
            return str(ts)
        if pd.isna(val):
            return ""
        return f"{float(val):.6g}"

    def _update_display_for_hourly_frame(self, frame: pd.DataFrame) -> None:
        cols = self._visible_display_columns(frame)
        self._table.clearContents()
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels(cols)
        n = len(frame)
        self._table.setRowCount(n)
        sub = frame[cols] if cols else frame
        for r in range(n):
            for cidx, col in enumerate(cols):
                val = sub.iloc[r, cidx]
                self._table.setItem(
                    r, cidx, QTableWidgetItem(self._format_cell_text(col, val))
                )

        whe = frame["WHE"]
        arr = np.asarray(whe.values, dtype=np.float64)
        self._stat_mean.setText(f"均值：{float(np.nanmean(arr)):.6g}")
        self._stat_max.setText(f"最大值：{float(np.nanmax(arr)):.6g}")
        self._stat_min.setText(f"最小值：{float(np.nanmin(arr)):.6g}")

        self._ax.clear()
        y = np.asarray(whe.values, dtype=np.float64)
        if "date" in frame.columns:
            x_dt = pd.to_datetime(frame["date"], utc=False)
            self._ax.plot(x_dt, y, color="tab:blue", linewidth=1.0)
            self._figure.autofmt_xdate()
            self._ax.set_xlabel("时间")
        else:
            x = np.arange(len(y), dtype=np.float64)
            self._ax.plot(x, y, color="tab:blue", linewidth=1.0)
            self._ax.set_xlabel("采样点")
        self._ax.set_ylabel("WHE（kWh）")
        self._ax.set_title("WHE 小时序列")
        self._ax.grid(True, alpha=0.3)
        self._chart_canvas.draw_idle()

    def process_csv_path(self, path: Union[str, Path]) -> None:
        """供测试与「选择文件」调用：读取并处理 CSV，成功则 ``prepared_hourly_ready`` 发出 ``pd.Series``。"""
        p = Path(path)
        self._status.setText(f"已选择：{p}")

        try:
            prepared = load_and_prepare_csv(p)
        except UnicodeDecodeError:
            QMessageBox.warning(
                self,
                "CSV 读取失败",
                "无法以 UTF-8 解码该文件，请另存为 UTF-8 编码后重试。",
            )
            return
        except pd.errors.ParserError as exc:
            QMessageBox.warning(
                self,
                "CSV 解析失败",
                f"无法解析为表格：{exc}",
            )
            return
        except ValueError as exc:
            self._handle_value_error(exc)
            return
        except Exception as exc:  # noqa: BLE001 - 界面需兜底
            QMessageBox.warning(
                self,
                "处理失败",
                f"处理 CSV 时发生意外错误：{exc}",
            )
            return

        hourly = prepared.hourly
        frame = hourly.frame
        if "WHE" not in frame.columns:
            QMessageBox.warning(self, "数据异常", "小时级结果中缺少 WHE 列。")
            return

        whe = frame["WHE"]
        if "date" in frame.columns:
            idx = pd.to_datetime(frame["date"], utc=False)
            series = pd.Series(whe.values, index=pd.DatetimeIndex(idx), name="WHE")
        else:
            series = pd.Series(whe.values, name="WHE")

        self._status.setText(f"处理成功：{p}（小时级 {len(series)} 点）")
        self._update_display_for_hourly_frame(frame)
        self.prepared_hourly_ready.emit(series)

    def _handle_value_error(self, exc: ValueError) -> None:
        msg = str(exc)
        if msg == MISSING_TIME_CONTEXT_ERROR or MISSING_TIME_CONTEXT_ERROR in msg:
            QMessageBox.warning(
                self,
                "缺少时间列",
                "CSV 无 date 列时，需填写起始时间与原始采样频率；该交互暂未接入，"
                "请手动补时间参数或改用带 date 列的 CSV。",
            )
            return
        if "缺少必填列" in msg:
            QMessageBox.warning(self, "列校验失败", msg)
            return
        if "无法解析为有效时间" in msg or "INVALID_DATE" in msg:
            QMessageBox.warning(self, "日期列无效", msg)
            return
        QMessageBox.warning(self, "处理失败", msg)

    def reset_session_state(self) -> None:
        self._status.setText("未选择文件。")
        self._table.clearContents()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._stat_mean.setText("均值：—")
        self._stat_max.setText("最大值：—")
        self._stat_min.setText("最小值：—")
        self._ax.clear()
        self._chart_canvas.draw_idle()
        self._show_table_view()

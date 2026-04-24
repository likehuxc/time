"""预测工作台：模型选择、预测执行与结果导出。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

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
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.forecast_service import ForecastService, ForecastUnavailableError
from services.record_service import save_prediction_record, update_prediction_record_output_path

HOUSEHOLD_AMPDS = "ampds"
HOUSEHOLD_LONDON_B0 = "london_b0"
MODEL_DC_ITRANSFORMER = "dc_itransformer"
MODEL_PATCHTST = "patchtst"
MODEL_TIMEXER = "timexer"

_HISTORY_DISPLAY_POINTS = 256


class ForecastPage(QWidget):
    """模型选择、预测天数、开始预测；摘要文本 + 历史/预测折线图。"""

    prediction_records_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = ForecastService()
        self._current_username: Optional[str] = None
        self._prepared_datetime_index: Optional[pd.DatetimeIndex] = None
        self._prepared_series_values: Optional[np.ndarray] = None
        self._latest_prediction_values: Optional[np.ndarray] = None
        self._latest_export_index: Optional[list[object]] = None
        self._latest_record_id: Optional[int] = None
        self._latest_record_signature: Optional[tuple[str, str, str]] = None
        self._latest_record_context: Optional[dict[str, str]] = None

        self._household_combo = QComboBox(self)
        self._household_combo.setObjectName("forecastCombo")
        self._household_combo.addItem("单户", HOUSEHOLD_AMPDS)
        self._household_combo.addItem("多户", HOUSEHOLD_LONDON_B0)

        self._model_combo = QComboBox(self)
        self._model_combo.setObjectName("forecastCombo")

        self._horizon_combo = QComboBox(self)
        self._horizon_combo.setObjectName("forecastCombo")
        self._horizon_combo.addItem("1天", "1d")
        self._horizon_combo.addItem("7天", "7d")
        self._horizon_combo.addItem("30天", "30d")

        self._run_btn = QPushButton("开始预测", self)
        self._run_btn.setObjectName("primaryButton")
        self._run_btn.clicked.connect(self._on_run_clicked)

        self._export_btn = QPushButton("导出预测表格", self)
        self._export_btn.setObjectName("secondaryButton")
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.setEnabled(False)

        self._result_label = QLabel("尚未运行预测。")
        self._result_label.setWordWrap(True)
        self._result_label.setObjectName("forecastResultLabel")

        self._figure = Figure(figsize=(11.0, 7.0), layout="tight")
        self._chart_canvas = FigureCanvasQTAgg(self._figure)
        self._chart_canvas.setObjectName("forecastChartCanvas")
        self._ax = self._figure.add_subplot(111)
        self._ax.set_xlabel("采样点")
        self._ax.set_ylabel("用电量（kWh）")
        self._ax.grid(True, alpha=0.3)

        self._setup_fixed_model_options()

        top_bar = QWidget(self)
        top_bar.setObjectName("pageCard")
        top_row = QHBoxLayout(top_bar)
        top_row.addWidget(QLabel("户型"))
        top_row.addWidget(self._household_combo)
        top_row.addWidget(QLabel("模型"))
        top_row.addWidget(self._model_combo)
        top_row.addWidget(QLabel("预测周期"))
        top_row.addWidget(self._horizon_combo)
        top_row.addWidget(self._run_btn)
        top_row.addWidget(self._export_btn)
        top_row.addStretch(1)

        bottom_panel = QWidget(self)
        bottom_panel.setObjectName("summaryCard")
        bottom_layout = QVBoxLayout(bottom_panel)
        summary_title = QLabel("结果摘要")
        summary_title.setObjectName("sectionTitle")
        bottom_layout.addWidget(summary_title)
        bottom_layout.addWidget(self._result_label)

        layout = QVBoxLayout(self)
        layout.addWidget(top_bar)
        layout.addWidget(self._chart_canvas, stretch=3)
        layout.addWidget(bottom_panel, stretch=0)

    def set_current_user(self, username: str) -> None:
        self._current_username = username

    def clear_current_user(self) -> None:
        self._current_username = None

    def load_prepared_series(self, series: object) -> None:
        """由数据工作台注入已预处理的历史序列。"""
        self._prepared_datetime_index = None
        self._clear_export_state()
        if isinstance(series, pd.Series):
            values = np.asarray(series.values, dtype=np.float64)
            if isinstance(series.index, pd.DatetimeIndex):
                self._prepared_datetime_index = series.index.copy()
        else:
            values = np.asarray(series, dtype=np.float64)
        self._prepared_series_values = values.reshape(-1).copy()

    def _setup_fixed_model_options(self) -> None:
        self._model_combo.clear()
        self._model_combo.addItem("DC-iTransformer", MODEL_DC_ITRANSFORMER)
        self._model_combo.addItem("PatchTST", MODEL_PATCHTST)
        self._model_combo.addItem("TimeXer", MODEL_TIMEXER)

    def _resolve_internal_resource_id(self) -> Optional[str]:
        """将“户型 + 界面模型”映射为注册表中的资源 id。"""
        household = self._household_combo.currentData()
        model = self._model_combo.currentData()
        if not isinstance(household, str) or not isinstance(model, str):
            return None
        resource_map = {
            (HOUSEHOLD_AMPDS, MODEL_DC_ITRANSFORMER): "dc_itransformer_ampds",
            (HOUSEHOLD_AMPDS, MODEL_PATCHTST): "patchtst_ampds",
            (HOUSEHOLD_AMPDS, MODEL_TIMEXER): "timexer_ampds",
            (HOUSEHOLD_LONDON_B0, MODEL_DC_ITRANSFORMER): "dc_itransformer_londonb0",
            (HOUSEHOLD_LONDON_B0, MODEL_PATCHTST): "patchtst_londonb0",
            (HOUSEHOLD_LONDON_B0, MODEL_TIMEXER): "timexer_londonb0",
        }
        return resource_map.get((household, model))

    def _current_record_signature(self) -> tuple[str, str, str]:
        return (
            str(self._household_combo.currentData()),
            str(self._model_combo.currentData()),
            str(self._horizon_combo.currentData()),
        )

    def _build_prediction_summary(self, prediction: np.ndarray) -> str:
        pred = np.asarray(prediction, dtype=np.float64).reshape(-1)
        peak_tip = self._build_peak_usage_tip(pred)
        return (
            f"预测均值：{float(pred.mean()):.4f}；"
            f"最大值：{float(pred.max()):.4f}；"
            f"最小值：{float(pred.min()):.4f}。\n"
            f"{peak_tip}"
        )

    def _build_peak_usage_tip(self, prediction: np.ndarray) -> str:
        pred = np.asarray(prediction, dtype=np.float64).reshape(-1)
        peak_index = int(np.argmax(pred))
        horizon = self._horizon_combo.currentData()

        if horizon == "1d":
            return (
                f"用电高峰提醒：预计 1 天内高峰出现在第 {peak_index + 1} 个小时，"
                "建议提前规划高负载用电。"
            )

        if horizon == "7d":
            peak_day = peak_index // 24 + 1
            return f"用电高峰提醒：预计高峰出现在 {peak_day} 天后，建议提前规划用电。"

        if horizon == "30d":
            peak_day = peak_index // 24 + 1
            return f"用电高峰提醒：预计高峰出现在 {peak_day} 天后，建议提前规划用电。"

        return "用电高峰提醒：预测结果已生成，建议结合高峰时段提前规划用电。"

    def _on_run_clicked(self) -> None:
        if self._model_combo.count() < 1:
            message = "没有可用模型配置，请先检查模型资源或配置。"
            QMessageBox.warning(self, "预测", message)
            self._result_label.setText(message)
            self._clear_export_state()
            self._clear_chart()
            return

        internal_id = self._resolve_internal_resource_id()
        if internal_id is None:
            message = "当前户型下该模型资源尚未接入，请切换户型或模型后重试。"
            QMessageBox.information(self, "预测", message)
            self._result_label.setText(message)
            self._clear_export_state()
            self._clear_chart()
            return

        horizon = self._horizon_combo.currentData()
        if not isinstance(horizon, str):
            message = "预测周期无效。"
            QMessageBox.warning(self, "预测", message)
            self._result_label.setText(message)
            self._clear_export_state()
            self._clear_chart()
            return

        if self._prepared_series_values is None or self._prepared_series_values.size < 1:
            message = "当前还未上传数据集。"
            QMessageBox.warning(self, "预测", message)
            self._result_label.setText(message)
            self._clear_export_state()
            self._clear_chart()
            return

        values = np.asarray(self._prepared_series_values, dtype=np.float64).reshape(-1)
        if (
            self._prepared_datetime_index is not None
            and len(self._prepared_datetime_index) == len(values)
        ):
            values_for_run: np.ndarray | pd.Series = pd.Series(
                values,
                index=self._prepared_datetime_index.copy(),
            )
        else:
            values_for_run = values

        try:
            out = self._service.run_forecast(internal_id, horizon, values_for_run)
        except ForecastUnavailableError as exc:
            QMessageBox.information(self, "预测不可用", str(exc))
            self._result_label.setText(str(exc))
            self._clear_export_state()
            self._clear_chart()
            return
        except ValueError as exc:
            QMessageBox.critical(self, "预测失败", str(exc))
            self._result_label.setText(str(exc))
            self._clear_export_state()
            self._clear_chart()
            return
        except Exception as exc:  # noqa: BLE001
            import traceback

            detail = f"{type(exc).__name__}: {exc}"
            message = f"预测失败，请检查模型资源或配置。\n\n{detail}"
            QMessageBox.critical(self, "预测失败", f"{message}\n\n{traceback.format_exc()}")
            self._result_label.setText(message)
            self._clear_export_state()
            self._clear_chart()
            return

        hist = np.asarray(out.history, dtype=np.float64).reshape(-1)
        pred = np.asarray(out.prediction, dtype=np.float64).reshape(-1)
        if pred.size < 1:
            self._result_label.setText("预测结果为空，无法绘图。")
            self._clear_export_state()
            self._clear_chart()
            return

        summary = self._build_prediction_summary(pred)
        self._result_label.setText(summary)
        self._latest_prediction_values = pred.copy()
        self._latest_export_index = self._build_export_index(int(pred.size))
        self._latest_record_context = {
            "model_id": internal_id,
            "horizon_key": horizon,
            "household_display": self._household_combo.currentText(),
            "display_model": self._model_combo.currentText(),
            "display_horizon": self._horizon_combo.currentText(),
            "summary": summary,
        }

        if self._current_username:
            current_signature = self._current_record_signature()
            should_create_record = (
                self._latest_record_id is None
                or self._latest_record_signature != current_signature
            )
            if should_create_record:
                try:
                    self._latest_record_id = save_prediction_record(
                        username=self._current_username,
                        model_id=self._latest_record_context["model_id"],
                        horizon_key=self._latest_record_context["horizon_key"],
                        template_path="(内存加载)",
                        output_path="/",
                        metrics_json=json.dumps(
                            {
                                "summary": self._latest_record_context["summary"],
                                "household_display": self._latest_record_context["household_display"],
                                "display_model": self._latest_record_context["display_model"],
                                "display_horizon": self._latest_record_context["display_horizon"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                except Exception:
                    pass
                else:
                    self._latest_record_signature = current_signature
                    self.prediction_records_changed.emit()

        self._export_btn.setEnabled(True)
        self._plot_history_and_prediction(hist, pred)

    def _on_export_clicked(self) -> None:
        if (
            self._latest_prediction_values is None
            or self._latest_export_index is None
            or self._latest_record_context is None
        ):
            return

        save_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出预测表格",
            self._default_export_filename(),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not save_path:
            return

        export_df = pd.DataFrame(
            {
                "日期": self._latest_export_index,
                "用电量": self._latest_prediction_values,
            }
        )
        try:
            export_df.to_csv(save_path, index=False, encoding="utf-8-sig")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(exc))
            return

        if self._latest_record_id is None or not self._current_username:
            return

        try:
            update_prediction_record_output_path(
                self._latest_record_id,
                save_path,
                username=self._current_username,
            )
        except Exception:
            pass

    def _default_export_filename(self) -> str:
        household = self._household_export_tag()
        model = self._sanitize_filename_part(self._model_combo.currentText(), "model")
        horizon = self._horizon_export_tag()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"forecast_{household}_{model}_{horizon}_{timestamp}.csv"

    def _household_export_tag(self) -> str:
        household = self._household_combo.currentData()
        mapping = {
            HOUSEHOLD_AMPDS: "single",
            HOUSEHOLD_LONDON_B0: "multi",
        }
        return mapping.get(household, "household")

    def _horizon_export_tag(self) -> str:
        horizon = self._horizon_combo.currentData()
        if isinstance(horizon, str) and horizon:
            return self._sanitize_filename_part(horizon, "horizon")
        return "horizon"

    @staticmethod
    def _sanitize_filename_part(value: str, fallback: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
        return sanitized or fallback

    def _clear_chart(self) -> None:
        self._ax.clear()
        self._ax.set_xlabel("采样点")
        self._ax.set_ylabel("用电量（kWh）")
        self._ax.grid(True, alpha=0.3)
        self._chart_canvas.draw_idle()

    def _plot_history_and_prediction(
        self, history: np.ndarray, prediction: np.ndarray
    ) -> None:
        self._ax.clear()
        hist = np.asarray(history, dtype=np.float64).reshape(-1)
        pred = np.asarray(prediction, dtype=np.float64).reshape(-1)
        hist_plot = hist[-_HISTORY_DISPLAY_POINTS:] if hist.size > _HISTORY_DISPLAY_POINTS else hist
        n_plot = int(hist_plot.size)

        x_hist = np.arange(n_plot, dtype=np.float64)
        x_pred = np.arange(n_plot, n_plot + int(pred.size), dtype=np.float64)
        self._ax.plot(x_hist, hist_plot, label="真实值", color="C0", linewidth=1.2)
        self._ax.plot(x_pred, pred, label="预测值", color="C1", linewidth=1.2)
        if n_plot > 0 and pred.size > 0:
            self._ax.axvline(x=n_plot - 0.5, color="0.5", linestyle=":", linewidth=0.8)
        self._ax.set_xlabel("采样点")
        self._ax.set_ylabel("用电量（kWh）")
        self._ax.grid(True, alpha=0.3)
        self._ax.legend(loc="upper right", fontsize=8)
        self._figure.tight_layout()
        self._chart_canvas.draw_idle()

    def _clear_export_state(self) -> None:
        self._latest_prediction_values = None
        self._latest_export_index = None
        self._latest_record_id = None
        self._latest_record_signature = None
        self._latest_record_context = None
        if hasattr(self, "_export_btn"):
            self._export_btn.setEnabled(False)

    def reset_session_state(self) -> None:
        self.clear_current_user()
        self._prepared_datetime_index = None
        self._prepared_series_values = None
        self._result_label.setText("尚未运行预测。")
        self._clear_export_state()
        self._clear_chart()

    def _build_export_index(self, prediction_size: int) -> list[object]:
        if (
            self._prepared_datetime_index is not None
            and len(self._prepared_datetime_index) >= 1
        ):
            last_timestamp = pd.Timestamp(self._prepared_datetime_index[-1])
            return [
                last_timestamp + pd.Timedelta(hours=step)
                for step in range(1, prediction_size + 1)
            ]
        return list(range(1, prediction_size + 1))

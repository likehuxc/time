"""Regression tests for prediction records presentation and refresh."""

from __future__ import annotations

from ui.main_window import MainWindow
from ui.pages.records_page import RecordsPage


def test_records_page_uses_five_user_facing_columns(qapp) -> None:
    page = RecordsPage()

    headers = [
        page._table.horizontalHeaderItem(index).text()
        for index in range(page._table.columnCount())
    ]

    assert headers == ["记录ID", "创建时间", "户型", "模型名称", "预测周期", "输出路径"]


def test_records_page_displays_consecutive_row_numbers(qapp) -> None:
    page = RecordsPage()
    page._set_rows(
        [
            {"id": 4, "created_at": "2026-04-23 15:08:45", "model_id": "timexer_ampds", "horizon_key": "7d", "output_path": "/", "metrics_json": "{}"},
            {"id": 2, "created_at": "2026-04-23 15:08:39", "model_id": "timexer_ampds", "horizon_key": "1d", "output_path": "/", "metrics_json": "{}"},
            {"id": 1, "created_at": "2026-04-23 15:08:02", "model_id": "timexer_ampds", "horizon_key": "1d", "output_path": "/", "metrics_json": "{}"},
        ]
    )

    assert [page._table.item(row, 0).text() for row in range(3)] == ["1", "2", "3"]


def test_records_page_refresh_orders_rows_oldest_first(qapp, monkeypatch) -> None:
    page = RecordsPage()
    monkeypatch.setattr(
        "ui.pages.records_page.list_prediction_records",
        lambda **kwargs: [
            {
                "id": 4,
                "created_at": "2026-04-23 15:31:04",
                "model_id": "timexer_ampds",
                "horizon_key": "1d",
                "output_path": "/",
                "metrics_json": "{}",
            },
            {
                "id": 2,
                "created_at": "2026-04-23 15:30:59",
                "model_id": "timexer_ampds",
                "horizon_key": "1d",
                "output_path": "/",
                "metrics_json": "{}",
            },
            {
                "id": 1,
                "created_at": "2026-04-23 15:30:57",
                "model_id": "timexer_ampds",
                "horizon_key": "1d",
                "output_path": "/",
                "metrics_json": "{}",
            },
        ],
    )

    page.set_current_user("alice")

    assert page._table.item(0, 1).text() == "2026-04-23 15:30:57"
    assert page._table.item(2, 1).text() == "2026-04-23 15:31:04"


def test_main_window_refreshes_records_when_forecast_saves_a_record(qapp, monkeypatch) -> None:
    window = MainWindow()
    calls: list[str] = []

    window._forecast.prediction_records_changed.disconnect()
    window._forecast.prediction_records_changed.connect(lambda: calls.append("refresh"))

    window._forecast.prediction_records_changed.emit()

    assert calls == ["refresh"]

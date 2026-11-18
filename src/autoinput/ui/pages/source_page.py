from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QSpinBox, QTableView

from autoinput.domain import SourceOptions
from autoinput.ui.pages.base import WizardPage, configure_table, message_label, set_message
from autoinput.ui.state import AppState, SourceData, read_source
from autoinput.ui.widgets.drop_zone import DropZone
from autoinput.ui.widgets.records_model import RecordsModel
from autoinput.ui.worker import BackgroundTask

PREVIEW_ROWS = 200


class SourcePage(WizardPage):
    title = "1. Chọn nguồn dữ liệu"
    description = "Chọn file cần nhập, xem trước dữ liệu rồi tiếp tục sang bước ánh xạ."

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self._path: Path | None = None
        self._options = SourceOptions()
        self._task: BackgroundTask | None = None
        self._pending: tuple[Path, SourceOptions] | None = None

        self.drop = DropZone()
        self.drop.file_selected.connect(self._open)

        self.sheet = QComboBox()
        self.sheet.setMinimumWidth(140)
        self.sheet.setToolTip("Sheet trong file Excel")
        self.header_row = QSpinBox(minimum=1, maximum=1000, value=1)
        self.header_row.setMinimumWidth(100)
        self.header_row.setToolTip("Dòng chứa tiêu đề cột")
        settings = QGroupBox("Tuỳ chọn đọc file")
        opts = QFormLayout(settings)
        self._opts = opts
        opts.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        opts.addRow("Sheet:", self.sheet)
        opts.addRow("Dòng tiêu đề:", self.header_row)
        self.sheet.currentIndexChanged.connect(self._reload)
        self.header_row.valueChanged.connect(self._reload)

        self.info = message_label()
        self.info.setText("Chưa có dữ liệu. Chọn file phía trên để xem các dòng và cột tại đây.")
        self.model = RecordsModel()
        table = QTableView()
        table.setModel(self.model)
        configure_table(table)

        row = QHBoxLayout()
        row.addWidget(self.drop, 2)
        row.addWidget(settings, 1)
        self.root.addLayout(row)
        self.root.addWidget(self.info)
        self.root.addWidget(table, 1)
        self._toggle_options(False)

    def browse(self) -> None:
        self.drop.browse()

    def is_complete(self) -> bool:
        return bool(self.state.records) and not self.state.source_busy

    @property
    def is_busy(self) -> bool:
        return self._task is not None

    def cancel(self) -> None:
        self._pending = None
        if self._task:
            self._task.cancel()

    def _toggle_options(self, is_excel: bool) -> None:
        self.sheet.setEnabled(is_excel)
        self._opts.setRowVisible(self.sheet, is_excel)

    def _open(self, path: Path) -> None:
        self._path = path
        self._options = SourceOptions(header_row=self.header_row.value())
        self.drop.show_file(path)
        is_excel = path.suffix.lower() in {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}
        self.sheet.blockSignals(True)
        self.sheet.clear()
        self.sheet.blockSignals(False)
        self._toggle_options(is_excel)
        self._reload()

    def apply_options(self, value: object) -> None:
        assert isinstance(value, SourceOptions)
        self._options = value.model_copy(deep=True)
        self.header_row.blockSignals(True)
        self.header_row.setValue(value.header_row)
        self.header_row.blockSignals(False)
        self.sheet.blockSignals(True)
        self.sheet.clear()
        if isinstance(value.sheet, str):
            self.sheet.addItem(value.sheet)
        self.sheet.blockSignals(False)
        self._reload()

    def _reload(self) -> None:
        if not self._path:
            return
        existing = self._options.model_dump()
        options = SourceOptions(
            **{
                **existing,
                "sheet": self.sheet.currentText() or self._options.sheet,
                "header_row": self.header_row.value(),
            }
        )
        self._options = options
        self._pending = (self._path, options)
        self.state.source_busy = True
        self.state.set_source(None)
        self.model.set_data([], [])
        set_message(self.info, "Đang đọc file… Bạn có thể chọn file khác hoặc thay đổi tuỳ chọn.")
        if self._task:
            self._task.cancel()
        else:
            self._start_load()
        self.complete_changed.emit()

    def _start_load(self) -> None:
        if self._pending is None:
            return
        path, options = self._pending
        self._pending = None
        self._task = BackgroundTask(lambda control: read_source(path, options, control), self)
        self._task.result.connect(self._loaded)
        self._task.failed.connect(self._failed)
        self._task.finished.connect(self._load_finished)
        self._task.start()

    def _loaded(self, result: object) -> None:
        assert isinstance(result, SourceData)
        self.state.set_source(result)
        self.sheet.blockSignals(True)
        self.sheet.clear()
        self.sheet.addItems(result.sheets)
        if isinstance(result.source.options.sheet, str):
            self.sheet.setCurrentText(result.source.options.sheet)
        else:
            self.sheet.setCurrentIndex(result.source.options.sheet)
        self.sheet.blockSignals(False)
        self.model.set_data(self.state.columns, self.state.records[:PREVIEW_ROWS])
        set_message(
            self.info,
            f"✔ {len(self.state.records)} dòng • {len(self.state.columns)} cột "
            f"• định dạng {result.source.label}"
            + (
                f" (hiển thị {PREVIEW_ROWS} dòng đầu)"
                if len(self.state.records) > PREVIEW_ROWS
                else ""
            ),
            "ok",
        )

    def _failed(self, message: str) -> None:
        set_message(self.info, f"✖ {message}", "error")

    def _load_finished(self) -> None:
        assert self._task is not None
        self._task.deleteLater()
        self._task = None
        if self._pending:
            self._start_load()
        else:
            self.state.source_busy = False
        self.complete_changed.emit()

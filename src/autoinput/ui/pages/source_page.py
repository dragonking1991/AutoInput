from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QSpinBox, QTableView

from autoinput.domain import AutoInputError, SourceOptions
from autoinput.sources.excel_source import ExcelSource
from autoinput.ui.pages.base import WizardPage, message_label, set_message
from autoinput.ui.state import AppState
from autoinput.ui.widgets.drop_zone import DropZone
from autoinput.ui.widgets.records_model import RecordsModel

PREVIEW_ROWS = 200


class SourcePage(WizardPage):
    title = "1. Chọn nguồn dữ liệu"

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self._path: Path | None = None

        self.drop = DropZone()
        self.drop.file_selected.connect(self._open)

        self.sheet = QComboBox()
        self.sheet.setToolTip("Sheet trong file Excel")
        self.header_row = QSpinBox(minimum=1, maximum=1000, value=1)
        self.header_row.setToolTip("Dòng chứa tiêu đề cột")
        opts = QFormLayout()
        opts.addRow("Sheet:", self.sheet)
        opts.addRow("Dòng tiêu đề:", self.header_row)
        self.sheet.currentIndexChanged.connect(self._reload)
        self.header_row.valueChanged.connect(self._reload)

        self.info = message_label()
        self.model = RecordsModel()
        table = QTableView()
        table.setModel(self.model)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setStretchLastSection(True)

        row = QHBoxLayout()
        row.addWidget(self.drop, 2)
        row.addLayout(opts, 1)
        self.root.addLayout(row)
        self.root.addWidget(self.info)
        self.root.addWidget(table, 1)
        self._toggle_options(False)

    def browse(self) -> None:
        self.drop.browse()

    def is_complete(self) -> bool:
        return bool(self.state.records)

    def _toggle_options(self, is_excel: bool) -> None:
        self.sheet.setEnabled(is_excel)

    def _open(self, path: Path) -> None:
        self._path = path
        self.drop.show_file(path)
        is_excel = path.suffix.lower() in {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}
        self.sheet.blockSignals(True)
        self.sheet.clear()
        if is_excel:
            try:
                self.sheet.addItems(ExcelSource(path).sheet_names())
            except Exception as e:
                set_message(self.info, f"Không đọc được danh sách sheet: {e}", "error")
        self.sheet.blockSignals(False)
        self._toggle_options(is_excel)
        self._reload()

    def _reload(self) -> None:
        if not self._path:
            return
        options = SourceOptions(
            sheet=self.sheet.currentText() or 0,
            header_row=self.header_row.value(),
        )
        try:
            self.state.load_source(self._path, options)
        except AutoInputError as e:
            self.state.records = []
            self.model.set_data([], [])
            set_message(self.info, f"✖ {e.message}", "error")
        else:
            self.model.set_data(self.state.columns, self.state.records[:PREVIEW_ROWS])
            set_message(
                self.info,
                f"✔ {len(self.state.records)} dòng • {len(self.state.columns)} cột "
                f"• định dạng {type(self.state.source).label}"
                + (
                    f" (hiển thị {PREVIEW_ROWS} dòng đầu)"
                    if len(self.state.records) > PREVIEW_ROWS
                    else ""
                ),
                "ok",
            )
        self.complete_changed.emit()

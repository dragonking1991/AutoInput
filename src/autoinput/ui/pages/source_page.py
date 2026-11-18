from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTableView,
    QToolButton,
    QWidget,
)

from autoinput.domain import SourceOptions
from autoinput.sources.excel_source import ExcelPreview
from autoinput.ui.icons import icon
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
        self._excel_preview: ExcelPreview | None = None

        self.drop = DropZone()
        self.drop.file_selected.connect(self._open)

        self.sheet = QComboBox()
        self.sheet.setMinimumWidth(140)
        self.sheet_label = QLabel("Sheet:")
        self.sheet_button = QToolButton()
        self.sheet_button.setIcon(icon("down"))
        self.sheet_button.setAccessibleName("Chọn sheet")
        self.sheet_button.clicked.connect(self.sheet.showPopup)
        self.sheet_field = QWidget()
        sheet_layout = QHBoxLayout(self.sheet_field)
        sheet_layout.setContentsMargins(0, 0, 0, 0)
        sheet_layout.setSpacing(4)
        sheet_layout.addWidget(self.sheet, 1)
        sheet_layout.addWidget(self.sheet_button)
        self._update_sheet_hint()
        self.header_row = QSpinBox(minimum=1, maximum=1000, value=1)
        self.header_row.setObjectName("headerRow")
        self.header_row.lineEdit().setTextMargins(10, 0, 10, 0)
        self.header_row.setKeyboardTracking(False)
        self.header_row.setMinimumWidth(100)
        self.header_row.setToolTip(
            "Số dòng trong file gốc dùng làm tên cột để ánh xạ. "
            "Các dòng phía sau sẽ được đọc thành dữ liệu nhập."
        )
        settings = QGroupBox("Tuỳ chọn đọc file")
        opts = QFormLayout(settings)
        self._opts = opts
        opts.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        opts.addRow(self.sheet_label, self.sheet_field)
        opts.addRow("Dòng tiêu đề:", self.header_row)
        self.sheet.currentIndexChanged.connect(self._reload)
        self.header_row.valueChanged.connect(self._reload)

        self.info = message_label()
        self.info.setText("Chưa có dữ liệu. Chọn file phía trên để xem các dòng và cột tại đây.")
        self.model = RecordsModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        configure_table(self.table)
        self.preview_mode = QComboBox()
        self.preview_mode.addItems(["Bố cục Excel (giữ ô gộp)", "Dữ liệu nhập (sau dòng tiêu đề)"])
        self.preview_mode.currentIndexChanged.connect(self._show_preview)
        self.preview_hint = message_label()
        self.preview_hint.setText(
            "Bố cục Excel giữ vị trí và ô gộp, không sao chép định dạng/màu của file. "
            "Chọn Dòng tiêu đề rồi xem Dữ liệu nhập để kiểm tra các cột dùng cho auto."
        )

        row = QHBoxLayout()
        row.addWidget(self.drop, 2)
        row.addWidget(settings, 1)
        self.root.addLayout(row)
        self.root.addWidget(self.info)
        self.root.addWidget(self.preview_mode)
        self.root.addWidget(self.preview_hint)
        self.root.addWidget(self.table, 1)
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
        self._opts.setRowVisible(self.sheet_field, is_excel)
        self.preview_mode.setVisible(is_excel)
        self.preview_hint.setVisible(is_excel)

    def _open(self, path: Path) -> None:
        self._path = path
        self._options = SourceOptions(header_row=self.header_row.value())
        self.drop.show_file(path)
        is_excel = path.suffix.lower() in {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}
        self.sheet.blockSignals(True)
        self.sheet.clear()
        self.sheet.blockSignals(False)
        self._update_sheet_hint()
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
        self._update_sheet_hint()
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
        self._excel_preview = None
        self.table.clearSpans()
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
        self._update_sheet_hint()
        self._excel_preview = result.excel_preview
        self._show_preview()
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

    def _update_sheet_hint(self) -> None:
        count = self.sheet.count()
        self.sheet_label.setText(f"Sheet ({count}):" if count else "Sheet:")
        self.sheet_button.setVisible(count > 1)
        hint = (
            f"Có {count} sheet. Bấm để chọn sheet khác."
            if count > 1
            else "File chỉ có một sheet." if count == 1 else "Sheet trong file Excel"
        )
        self.sheet.setToolTip(hint)
        self.sheet_button.setToolTip(hint)
        self.sheet.setCursor(
            Qt.CursorShape.PointingHandCursor if count > 1 else Qt.CursorShape.ArrowCursor
        )

    def _show_preview(self) -> None:
        self.table.clearSpans()
        preview = self._excel_preview if self.preview_mode.currentIndex() == 0 else None
        self.table.setWordWrap(preview is not None)
        if preview is None:
            self.model.set_data(self.state.columns, self.state.records[:PREVIEW_ROWS])
            return
        self.model.set_data(preview.columns, preview.rows)
        for top, left, height, width in preview.spans:
            self.table.setSpan(top, left, height, width)

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

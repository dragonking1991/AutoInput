from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableView,
    QToolButton,
    QWidget,
)

from autoinput.domain import SourceOptions
from autoinput.sources.excel_source import ExcelPreview
from autoinput.ui.icons import icon
from autoinput.ui.pages.base import WizardPage, configure_table, message_label, set_message
from autoinput.ui.state import AppState, AutoLayout, SourceData, read_source
from autoinput.ui.widgets.drop_zone import DropZone
from autoinput.ui.widgets.records_model import RecordsModel
from autoinput.ui.widgets.sheet_model import (
    ROLE_STYLE,
    SheetDelegate,
    SheetModel,
    apply_sheet_geometry,
)
from autoinput.ui.worker import BackgroundTask

PREVIEW_ROWS = 200
EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}
RANGE_REASONS = {"", "trước dòng bắt đầu dữ liệu", "sau dòng kết thúc dữ liệu"}


def _number_box(tooltip: str, maximum: int) -> QSpinBox:
    box = QSpinBox(minimum=1, maximum=maximum, value=1)
    box.setObjectName("headerRow")
    box.lineEdit().setTextMargins(10, 0, 10, 0)
    box.setKeyboardTracking(False)
    box.setMinimumWidth(100)
    box.setToolTip(tooltip)
    return box


class SourcePage(WizardPage):
    title = "1. Chọn nguồn dữ liệu"
    description = "Chọn file cần nhập, xem trước dữ liệu rồi tiếp tục sang bước ánh xạ."

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self._path: Path | None = None
        self._options = SourceOptions()
        self._task: BackgroundTask | None = None
        self._pending: tuple[Path, SourceOptions, AutoLayout] | None = None
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
        self.header_row = _number_box(
            "Số dòng trong file gốc dùng làm tên cột để ánh xạ. "
            "Các dòng phía sau sẽ được đọc thành dữ liệu nhập.",
            100_000,
        )
        self.header_rows = _number_box(
            "Tiêu đề nhiều tầng (vd. “Phụ cấp” gộp trên “Tiền cơm”, “Xăng xe”): nhập số dòng "
            "tiêu đề để tên cột thành “Phụ cấp / Tiền cơm”.",
            10,
        )
        self.smart_rows = QCheckBox("Lọc thông minh")
        self.smart_rows.setToolTip(
            "Tự bỏ dòng đánh số cột (1, 2, 3…), dòng nhóm/mục (I. Giáo viên…), dòng Tổng/Cộng "
            "và phần chữ ký; điền giá trị ô gộp xuống các dòng bên dưới."
        )
        self.display_values = QCheckBox("Giữ định dạng số như Excel")
        self.display_values.setToolTip(
            "Nhập đúng như hiển thị trong Excel: 01, 1.000.000, 05/10/2024. "
            "Bỏ chọn để lấy giá trị thô (1, 1000000)."
        )
        self.detect_button = QPushButton("Tự nhận diện lại")
        self.detect_button.setIcon(icon("magic"))
        self.detect_button.setToolTip(
            "Tìm lại dòng tiêu đề, số tầng tiêu đề và các dòng cần bỏ qua"
        )
        self.detect_button.clicked.connect(lambda: self._reload("detect"))

        settings = QGroupBox("Tuỳ chọn đọc file")
        opts = QFormLayout(settings)
        self._opts = opts
        opts.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        opts.addRow(self.sheet_label, self.sheet_field)
        opts.addRow("Dòng tiêu đề:", self.header_row)
        opts.addRow("Số dòng tiêu đề:", self.header_rows)
        opts.addRow(self.smart_rows)
        opts.addRow(self.display_values)
        opts.addRow(self.detect_button)
        self.sheet.currentIndexChanged.connect(lambda: self._reload("detect"))
        self.header_row.valueChanged.connect(lambda: self._reload())
        self.header_rows.valueChanged.connect(lambda: self._reload())
        self.smart_rows.toggled.connect(lambda: self._reload())
        self.display_values.toggled.connect(lambda: self._reload())

        self.info = message_label()
        self.info.setText("Chưa có dữ liệu. Chọn file phía trên để xem các dòng và cột tại đây.")
        self.model = RecordsModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        configure_table(self.table)
        self.sheet_model = SheetModel()
        self.sheet_view = QTableView()
        self.sheet_view.setModel(self.sheet_model)
        self.sheet_view.setItemDelegate(SheetDelegate(self.sheet_view))
        self.sheet_view.setMinimumHeight(170)
        self.sheet_view.setShowGrid(True)
        # Excel rows are ~20px tall; the theme's 9px header padding would elide row numbers.
        self.sheet_view.setStyleSheet(
            "QTableView { gridline-color: #e3e7ee; }QHeaderView::section { padding: 0px 4px; }"
        )
        self.sheet_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.sheet_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sheet_view.customContextMenuRequested.connect(
            lambda pos: self._row_menu(self.sheet_view.rowAt(pos.y()), self.sheet_view, pos)
        )
        vertical = self.sheet_view.verticalHeader()
        vertical.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        vertical.customContextMenuRequested.connect(
            lambda pos: self._row_menu(vertical.logicalIndexAt(pos), vertical, pos)
        )
        self.views = QStackedWidget()
        self.views.addWidget(self.sheet_view)
        self.views.addWidget(self.table)

        self.preview_mode = QComboBox()
        self.preview_mode.addItems(
            ["Bố cục Excel (đúng định dạng file gốc)", "Dữ liệu nhập (từng dòng sẽ được nhập)"]
        )
        self.preview_mode.currentIndexChanged.connect(self._show_preview)
        legend = "  ".join(
            f"<span style='color:{color}'>■</span> {label}"
            for role, (color, label) in ROLE_STYLE.items()
            if role != "title"
        )
        self.preview_hint = message_label()
        self.preview_hint.setTextFormat(Qt.TextFormat.RichText)
        self.preview_hint.setText(
            f"{legend}<br>Chuột phải vào dòng để đặt tiêu đề, nơi bắt đầu/kết thúc dữ liệu "
            "hoặc bỏ qua/nhập lại các dòng đã chọn."
        )
        self.layout_summary = message_label()
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.preview_mode)
        mode_row.addWidget(self.layout_summary, 1)

        row = QHBoxLayout()
        row.addWidget(self.drop, 2)
        row.addWidget(settings, 1)
        self.root.addLayout(row)
        self.root.addWidget(self.info)
        self.root.addLayout(mode_row)
        self.root.addWidget(self.preview_hint)
        self.root.addWidget(self.views, 1)
        self._set_widgets(self._options)
        self._toggle_options(False)

    def browse(self) -> None:
        self.drop.browse()

    def is_complete(self) -> bool:
        return bool(self.state.records) and not self.state.source_busy

    @property
    def is_busy(self) -> bool:
        return self._task is not None

    @property
    def current_table(self) -> QTableView:
        return self.table if self.views.currentWidget() is self.table else self.sheet_view

    def cancel(self) -> None:
        self._pending = None
        if self._task:
            self._task.cancel()

    def _toggle_options(self, is_excel: bool) -> None:
        self.sheet.setEnabled(is_excel)
        for widget in (
            self.sheet_field,
            self.header_rows,
            self.smart_rows,
            self.display_values,
            self.detect_button,
        ):
            self._opts.setRowVisible(widget, is_excel)
        self.preview_mode.setVisible(is_excel)
        self.preview_hint.setVisible(is_excel)
        self.layout_summary.setVisible(is_excel)
        if not is_excel:
            self.views.setCurrentWidget(self.table)

    def _set_widgets(self, options: SourceOptions) -> None:
        for widget, value in (
            (self.header_row, options.header_row),
            (self.header_rows, options.header_rows),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        for check, flag in (
            (self.smart_rows, options.smart_rows),
            (self.display_values, options.display_values),
        ):
            check.blockSignals(True)
            check.setChecked(flag)
            check.blockSignals(False)

    def _open(self, path: Path) -> None:
        self._path = path
        self._options = SourceOptions()
        self._set_widgets(self._options)
        self.drop.show_file(path)
        is_excel = path.suffix.lower() in EXCEL_SUFFIXES
        self.sheet.blockSignals(True)
        self.sheet.clear()
        self.sheet.blockSignals(False)
        self._update_sheet_hint()
        self._toggle_options(is_excel)
        self._reload("remember" if is_excel else "off")

    def apply_options(self, value: object) -> None:
        assert isinstance(value, SourceOptions)
        self._options = value.model_copy(deep=True)
        self._set_widgets(value)
        self.sheet.blockSignals(True)
        self.sheet.clear()
        if isinstance(value.sheet, str):
            self.sheet.addItem(value.sheet)
        self.sheet.blockSignals(False)
        self._update_sheet_hint()
        self._reload()

    def _widget_options(self) -> SourceOptions:
        return SourceOptions(
            **{
                **self._options.model_dump(),
                "sheet": self.sheet.currentText() or self._options.sheet,
                "header_row": self.header_row.value(),
                "header_rows": self.header_rows.value(),
                "smart_rows": self.smart_rows.isChecked(),
                "display_values": self.display_values.isChecked(),
            }
        )

    def _reload(self, auto: AutoLayout = "off", options: SourceOptions | None = None) -> None:
        if not self._path:
            return
        options = options or self._widget_options()
        self._options = options
        self._pending = (self._path, options, auto)
        self.state.source_busy = True
        self.state.set_source(None)
        self._excel_preview = None
        self.sheet_view.clearSpans()
        self.sheet_model.set_preview(None)
        self.model.set_data([], [])
        self.layout_summary.clear()
        set_message(self.info, "Đang đọc file… Bạn có thể chọn file khác hoặc thay đổi tuỳ chọn.")
        if self._task:
            self._task.cancel()
        else:
            self._start_load()
        self.complete_changed.emit()

    def _start_load(self) -> None:
        if self._pending is None:
            return
        path, options, auto = self._pending
        self._pending = None
        self._task = BackgroundTask(lambda control: read_source(path, options, control, auto), self)
        self._task.result.connect(self._loaded)
        self._task.failed.connect(self._failed)
        self._task.finished.connect(self._load_finished)
        self._task.start()

    def _loaded(self, result: object) -> None:
        assert isinstance(result, SourceData)
        options = result.source.options
        self._options = options.model_copy(deep=True)
        self._set_widgets(options)
        self.state.set_source(result)
        self.sheet.blockSignals(True)
        self.sheet.clear()
        self.sheet.addItems(result.sheets)
        if isinstance(options.sheet, str):
            self.sheet.setCurrentText(options.sheet)
        else:
            self.sheet.setCurrentIndex(options.sheet)
        self.sheet.blockSignals(False)
        self._update_sheet_hint()
        self._excel_preview = result.excel_preview
        self._show_preview()
        layout = result.excel_preview.layout if result.excel_preview else None
        self.layout_summary.setText(layout.summary() if layout else "")
        note = f" • {result.note}" if result.note else ""
        set_message(
            self.info,
            f"✔ {len(self.state.records)} dòng • {len(self.state.columns)} cột "
            f"• định dạng {result.source.label}{note}",
            "ok",
        )

    def _update_sheet_hint(self) -> None:
        count = self.sheet.count()
        self.sheet_label.setText(f"Sheet ({count}):" if count else "Sheet:")
        self.sheet_button.setVisible(count > 1)
        hint = (
            f"Có {count} sheet. Bấm để chọn sheet khác."
            if count > 1
            else "File chỉ có một sheet."
            if count == 1
            else "Sheet trong file Excel"
        )
        self.sheet.setToolTip(hint)
        self.sheet_button.setToolTip(hint)
        self.sheet.setCursor(
            Qt.CursorShape.PointingHandCursor if count > 1 else Qt.CursorShape.ArrowCursor
        )

    def _show_preview(self) -> None:
        preview = self._excel_preview if self.preview_mode.currentIndex() == 0 else None
        self.model.set_data(self.state.columns, self.state.records[:PREVIEW_ROWS])
        self.sheet_view.clearSpans()
        if preview is None:
            self.views.setCurrentWidget(self.table)
            return
        self.sheet_model.set_preview(preview)
        apply_sheet_geometry(self.sheet_view, preview)
        self.views.setCurrentWidget(self.sheet_view)

    # ── row actions (Excel layout view) ──
    def _selected_rows(self, clicked: int) -> list[int]:
        rows = {i.row() for i in self.sheet_view.selectionModel().selectedIndexes()}
        return sorted(rows if clicked in rows else {clicked})

    def _row_menu(self, row: int, widget: QWidget, pos: QPoint) -> None:
        menu = self.row_menu(row)
        if menu is not None:
            menu.exec(widget.mapToGlobal(pos))

    def row_menu(self, row: int) -> QMenu | None:
        preview = self._excel_preview
        if row < 0 or preview is None or preview.layout is None:
            return None
        n = preview.rows[row].index
        options = self._options
        rows = self._selected_rows(row)
        roles = [self.sheet_model.role_of(r) for r in rows]
        numbers = [preview.rows[r].index for r in rows]
        menu = QMenu(self)

        def add(text: str, **update: object) -> QAction:
            action = menu.addAction(text)
            action.triggered.connect(
                lambda: self._reload(options=options.model_copy(update=update))
            )
            return action

        add(f"Đặt dòng {n} làm tiêu đề", header_row=n, header_rows=1, data_start=None)
        if 0 < n - options.header_row < 10:
            add(
                f"Tiêu đề gồm dòng {options.header_row}–{n} (nhiều tầng)",
                header_rows=n - options.header_row + 1,
            )
        menu.addSeparator()
        add(f"Dữ liệu bắt đầu từ dòng {n}", data_start=n)
        add(f"Dữ liệu kết thúc ở dòng {n}", data_end=n)
        data = [num for num, (role, _) in zip(numbers, roles, strict=True) if role == "data"]
        skipped = [
            num
            for num, (role, reason) in zip(numbers, roles, strict=True)
            if role == "skip" and reason not in RANGE_REASONS
        ]
        if data or skipped:
            menu.addSeparator()
        if data:
            add(
                f"Bỏ qua {len(data)} dòng đã chọn" if len(data) > 1 else f"Bỏ qua dòng {n}",
                skip_rows=sorted(set(options.skip_rows) | set(data)),
                include_rows=sorted(set(options.include_rows) - set(data)),
            )
        if skipped:
            add(
                f"Nhập lại {len(skipped)} dòng đang bỏ qua"
                if len(skipped) > 1
                else f"Nhập lại dòng {skipped[0]}",
                skip_rows=sorted(set(options.skip_rows) - set(skipped)),
                include_rows=sorted(set(options.include_rows) | set(skipped)),
            )
        menu.addSeparator()
        if options.data_start or options.data_end or options.skip_rows or options.include_rows:
            add(
                "Xoá các chỉnh tay (bắt đầu/kết thúc/bỏ qua)",
                data_start=None,
                data_end=None,
                skip_rows=[],
                include_rows=[],
            )
        detect = menu.addAction(icon("magic"), "Tự nhận diện lại bảng")
        detect.triggered.connect(lambda: self._reload("detect"))
        return menu

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

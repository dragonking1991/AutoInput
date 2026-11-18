from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QWidget,
)

from autoinput.domain import (
    AutoInputError,
    ConfigError,
    FieldMap,
    Mapping,
    Profile,
    Record,
    RowStatus,
)
from autoinput.engine import RunControl
from autoinput.infra.settings import get_settings
from autoinput.infra.storage import list_profiles, load_mapping, load_profile, save_mapping
from autoinput.infra.templates import TemplateMemory
from autoinput.mapping import Mapper, suggest_mapping, suggest_transforms
from autoinput.sources.excel_source import ExcelSource
from autoinput.transforms import apply_transforms, transform_registry
from autoinput.ui.icons import icon
from autoinput.ui.pages.base import WizardPage, configure_table, message_label, set_message
from autoinput.ui.state import AppState
from autoinput.ui.theme import STATUS_COLORS
from autoinput.ui.widgets.records_model import RecordsModel
from autoinput.ui.worker import BackgroundTask

UNUSED = "— không dùng —"
PREVIEW_ROWS = 200
COL_FIELD, COL_SOURCE, COL_REQUIRED, COL_TRANSFORMS, COL_EXAMPLE = range(5)
SAMPLE_ROWS = 50
TRANSFORM_PRESETS = [
    ("Bỏ khoảng trắng đầu/cuối", "strip"),
    ("Gộp khoảng trắng thừa", "collapse_spaces"),
    ("VIẾT HOA", "upper"),
    ("viết thường", "lower"),
    ("Viết Hoa Chữ Đầu", "title"),
    ("Bỏ dấu tiếng Việt", "no_accents"),
    ("Chỉ giữ chữ số", "digits"),
    ("Số tiền 1.000.000 → 1000000", "replace:.,"),
    ("Số điện thoại Việt Nam", "phone_vn"),
    ("Ngày → 31/12/2024", "date:%d/%m/%Y"),
    ("Ngày → 2024-12-31", "date:%Y-%m-%d"),
    ("Thêm số 0 đầu (vd. 5 chữ số)", "pad_left:5,0"),
    ("Đổi mã (sửa lại cặp giá trị)", "map:M=Nam,F=Nữ"),
]
UNMAPPED_BG = QColor("#fff7e6")


@dataclass
class ValidationResult:
    columns: list[str]
    rows: list[Record]
    errors: list[tuple[int, str]]
    invalid_count: int
    first_invalid: list[int]
    total: int


def validate_records(
    mapper: Mapper, records: list[Record], control: RunControl
) -> ValidationResult:
    result = ValidationResult(
        [fm.field for fm in mapper.mapping.fields], [], [], 0, [], len(records)
    )
    labels = {name: spec.label or name for name, spec in mapper.profile.fields.items()}
    for record in records:
        control.checkpoint()
        item = mapper.apply(record)
        if len(result.rows) < PREVIEW_ROWS:
            result.rows.append(Record(record.index, {**item.values, **item.errors}))
            if not item.ok:
                result.errors.append(
                    (
                        record.index,
                        "; ".join(f"{labels.get(k, k)}: {v}" for k, v in item.errors.items()),
                    )
                )
        if not item.ok:
            result.invalid_count += 1
            if len(result.first_invalid) < 10:
                result.first_invalid.append(record.index)
    return result


class MappingPage(WizardPage):
    title = "2. Ánh xạ & kiểm tra"
    description = "Ghép cột nguồn với trường trong ứng dụng đích. Kiểm tra dữ liệu trước khi chạy."
    source_options_requested = Signal(object)

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self._profiles: dict[str, Path] = {}
        self._base_mapping: Mapping | None = None
        self._editors: dict[str, tuple[QComboBox, QCheckBox, QLineEdit]] = {}
        self._samples: dict[str, list[str]] = {}
        self._memory = TemplateMemory()
        self._task: BackgroundTask | None = None
        self._validation_requested = False
        self._debounce = QTimer(self, singleShot=True, interval=300)
        self._debounce.timeout.connect(self._rebuild_mapping)

        self.profile_box = QComboBox()
        self.profile_box.setMinimumWidth(200)
        self.profile_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.profile_box.setMinimumContentsLength(18)
        self.profile_box.currentIndexChanged.connect(self._on_profile_changed)
        self.profile_hint = message_label()
        self.profile_hint.setText("Chọn ứng dụng/biểu mẫu cần nhập để bắt đầu ghép cột.")
        suggest = QPushButton("Gợi ý lại")
        suggest.setIcon(icon("mapping"))
        suggest.setToolTip("Tự ghép cột nguồn với trường đích theo tên (không phân biệt dấu)")
        suggest.clicked.connect(self._auto_suggest)
        open_btn = QPushButton("Mở cấu hình…")
        open_btn.setIcon(icon("file"))
        open_btn.setToolTip("Mở file mapping YAML đã lưu")
        open_btn.clicked.connect(self._open_mapping)
        save_btn = QPushButton("Lưu cấu hình…")
        save_btn.setIcon(icon("save"))
        save_btn.setToolTip("Lưu cách ghép cột để lần sau tự nạp lại")
        save_btn.clicked.connect(self._save_mapping)
        target_row = QFormLayout()
        target_row.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        target_row.addRow("Ứng dụng đích:", self.profile_box)
        bar = QHBoxLayout()
        for w in (suggest, open_btn, save_btn):
            bar.addWidget(w)
        bar.addStretch()

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Trường đích", "Lấy từ cột", "Bắt buộc", "Biến đổi (tuỳ chọn)", "Ví dụ kết quả"]
        )
        configure_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_REQUIRED, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        self.mapped_info = message_label()
        self.summary = message_label()
        self.preview_model = RecordsModel(
            with_status=True, status_overrides={"pending": ("Hợp lệ", STATUS_COLORS["done"])}
        )
        preview = QTableView()
        preview.setModel(self.preview_model)
        configure_table(preview)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table)
        split.addWidget(preview)
        self.root.addLayout(target_row)
        self.root.addWidget(self.profile_hint)
        self.root.addLayout(bar)
        self.root.addWidget(self.mapped_info)
        self.root.addWidget(split, 1)
        self.root.addWidget(self.summary)

        self._reload_profiles()
        self.state.source_changed.connect(self._source_changed)

    # ── lifecycle ──
    def on_enter(self) -> None:
        # Edits and source changes already re-validate; re-filling here would discard nothing
        # useful but cost a full re-check of every row on each navigation.
        if self.state.profile and not self._editors:
            self._fill_table(self.state.profile, self.state.mapping)

    def is_complete(self) -> bool:
        return (
            self.state.validated
            and not self.state.validation_pending
            and not self.state.source_busy
            and bool(self.state.records)
        )

    @property
    def is_busy(self) -> bool:
        return self._task is not None

    def cancel(self) -> None:
        self._debounce.stop()
        self._validation_requested = False
        if self._task:
            self._task.cancel()

    def flush_edits(self) -> None:
        if self._debounce.isActive():
            self._debounce.stop()
            self._rebuild_mapping()

    def _source_changed(self) -> None:
        self._debounce.stop()
        if self.state.source and self.state.profile:
            mapping = self.state.mapping
            if mapping:
                mapping = mapping.model_copy(
                    update={"source_options": self.state.source.options.model_copy(deep=True)}
                )
            self._fill_table(self.state.profile, mapping)
        elif self.state.source and (remembered := self._memory.mapping(self.state.columns)):
            index = self.profile_box.findData(remembered[0])
            if index > 0:
                self.profile_box.setCurrentIndex(index)
            else:
                self._validate()
        else:
            self._validate()

    def _schedule_rebuild(self) -> None:
        self.state.validated = False
        self.state.validation_pending = True
        self._validation_requested = False
        if self._task:
            self._task.cancel()
        self._debounce.start()
        self.complete_changed.emit()

    # ── profiles ──
    def _reload_profiles(self) -> None:
        self._profiles = list_profiles(get_settings().profiles_path)
        self.profile_box.clear()
        self.profile_box.addItem("Chọn ứng dụng đích…", None)
        for pid, path in self._profiles.items():
            profile = load_profile(path)
            self.profile_box.addItem(profile.name, pid)
            self.profile_box.setItemData(
                self.profile_box.count() - 1,
                f"{profile.name}\nDriver: {profile.driver} • {len(profile.fields)} trường",
                Qt.ItemDataRole.ToolTipRole,
            )

    def _saved_mapping(self, profile: Profile) -> tuple[Mapping, Path] | None:
        """A saved mapping for this profile whose source columns all exist in the current file."""
        directory = get_settings().mappings_path
        preferred = directory / f"{profile.id}.yaml"
        paths = sorted(directory.glob("*.y*ml"), key=lambda p: p != preferred)
        columns = set(self.state.columns)
        for path in paths:
            try:
                mapping = load_mapping(path)
            except ConfigError:
                continue
            sources = {fm.source for fm in mapping.fields if fm.const is None and fm.source}
            if mapping.profile == profile.id and mapping.fields and sources <= columns:
                return mapping, path
        return None

    def _on_profile_changed(self) -> None:
        pid = self.profile_box.currentData()
        profile = load_profile(self._profiles[pid]) if pid else None
        remembered = self._memory.mapping(self.state.columns) if profile else None
        if profile and remembered and remembered[0] == profile.id:
            options = self.state.source.options if self.state.source else None
            mapping = remembered[1]
            if options:
                mapping = mapping.model_copy(update={"source_options": options})
            self._fill_table(profile, mapping)
            set_message(
                self.profile_hint,
                "✔ Đã tự nạp cách ghép cột đã nhớ cho file có cùng các cột — kiểm tra rồi "
                "bấm Tiếp. Bấm “Gợi ý lại” nếu muốn ghép tự động.",
                "ok",
            )
        elif profile:
            saved = self._saved_mapping(profile)
            if saved:
                mapping, path = saved
                # Keep how the current file is read; only the column/field rules are reused.
                options = self.state.source.options if self.state.source else None
                if options:
                    mapping = mapping.model_copy(update={"source_options": options})
                self._fill_table(profile, mapping)
                set_message(
                    self.profile_hint,
                    f"✔ Đã nạp cấu hình đã lưu “{path.name}” — dùng lại cách ghép cột và "
                    "quy tắc kiểm tra. Bấm “Gợi ý lại” nếu muốn ghép tự động.",
                    "ok",
                )
            else:
                self._fill_table(profile, None)
                self._auto_suggest()
        else:
            self._debounce.stop()
            self._base_mapping = None
            self._editors.clear()
            self.table.setRowCount(0)
            self.mapped_info.clear()
            self.state.set_mapping(None, None)
            set_message(self.profile_hint, "Chọn ứng dụng/biểu mẫu cần nhập để bắt đầu ghép cột.")
            self._validate()

    # ── table <-> Mapping ──
    def _fill_table(self, profile: Profile, mapping: Mapping | None) -> None:
        self._debounce.stop()
        self._base_mapping = mapping.model_copy(deep=True) if mapping else None
        self._editors.clear()
        existing = {fm.field: fm for fm in mapping.fields} if mapping else {}
        self._samples = {column: [] for column in self.state.columns}
        for record in self.state.records[:SAMPLE_ROWS]:
            for column, value in record.data.items():
                if value and column in self._samples:
                    self._samples[column].append(value)
        self.table.setRowCount(len(profile.fields))
        tooltip = (
            "Chuẩn hoá giá trị trước khi nhập, nhiều bước phân tách bằng ';'.\n"
            "Ví dụ: strip (bỏ khoảng trắng thừa) • title (Viết Hoa Chữ Đầu) • "
            "date:%d/%m/%Y (đổi định dạng ngày) • phone_vn (chuẩn hoá SĐT) • "
            "map:M=Nam,F=Nữ (đổi mã).\nCó sẵn: " + ", ".join(transform_registry.keys())
        )
        for row, (name, spec) in enumerate(profile.fields.items()):
            fm = existing.get(name)
            field_item = QTableWidgetItem((spec.label or name) + ("  🔒" if spec.sensitive else ""))
            field_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            field_item.setToolTip(
                f"Mã trường: {name}"
                + (" • dữ liệu nhạy cảm, bị che trong log" if spec.sensitive else "")
            )
            self.table.setItem(row, COL_FIELD, field_item)

            combo = QComboBox()
            combo.addItem(UNUSED)
            if fm and fm.const is not None:
                combo.addItem("Giá trị cố định (YAML)")
                combo.setCurrentIndex(1)
            for column in self.state.columns:
                sample = next(iter(self._samples.get(column, [])), "")
                text = f"{column}  ·  vd: {_short(sample)}" if sample else column
                combo.addItem(text, column)
                combo.setItemData(
                    combo.count() - 1,
                    f"{column}\nVí dụ: " + ", ".join(map(_short, self._samples[column][:3]))
                    if sample
                    else f"{column}\n(cột trống trong {SAMPLE_ROWS} dòng đầu)",
                    Qt.ItemDataRole.ToolTipRole,
                )
            if fm and fm.const is None and fm.source:
                if combo.findData(fm.source) < 0:
                    combo.addItem(fm.source, fm.source)
                combo.setCurrentIndex(combo.findData(fm.source))
            if fm and fm.const is None and fm.source is None:
                combo.addItem("Giá trị mặc định (YAML)")
                combo.setCurrentIndex(combo.count() - 1)
            combo.currentIndexChanged.connect(self._schedule_rebuild)
            self.table.setCellWidget(row, COL_SOURCE, combo)

            req = QCheckBox()
            req.setChecked(bool(fm and fm.required))
            req.toggled.connect(self._schedule_rebuild)
            self.table.setCellWidget(row, COL_REQUIRED, _centered(req))

            tr = QLineEdit("; ".join(fm.transforms) if fm else "strip")
            tr.setToolTip(tooltip)
            tr.setPlaceholderText("vd: strip; title; date:%d/%m/%Y")
            tr.textChanged.connect(self._schedule_rebuild)
            self.table.setCellWidget(row, COL_TRANSFORMS, _with_presets(tr))
            example = QTableWidgetItem()
            example.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, COL_EXAMPLE, example)
            self._editors[name] = (combo, req, tr)
        self.state.profile = profile
        self._rebuild_mapping()

    def _rebuild_mapping(self) -> None:
        profile = self.state.profile
        if not profile:
            return
        fields: list[FieldMap] = []
        existing = {fm.field: fm for fm in self._base_mapping.fields} if self._base_mapping else {}
        for name, (combo, req, tr) in self._editors.items():
            if combo.currentIndex() == 0:
                continue
            source = combo.currentData()
            previous = existing.get(name, FieldMap(field=name))
            constant_selected = source is None and previous.const is not None
            text = tr.text()
            transforms = [t.strip() for t in text.split(";") if t.strip()]
            fields.append(
                previous.model_copy(
                    update={
                        "source": previous.source if constant_selected else source,
                        "const": previous.const if constant_selected else None,
                        "required": req.isChecked(),
                        "transforms": transforms,
                    }
                )
            )
        fields.extend(fm for name, fm in existing.items() if name not in profile.fields)
        options = (
            self._base_mapping.source_options
            if self._base_mapping
            else self.state.source.options
            if self.state.source
            else None
        )
        mapping = Mapping(
            name=self._base_mapping.name if self._base_mapping else profile.name,
            profile=profile.id,
            fields=fields,
            **({"source_options": options} if options else {}),
        )
        self.state.set_mapping(profile, mapping)
        self._update_examples()
        self._validate()

    def _update_examples(self) -> None:
        """Show the first sample after transforms and highlight fields left unmapped."""
        mapped = 0
        for row, (_name, (combo, _req, tr)) in enumerate(self._editors.items()):
            field_item, example = self.table.item(row, COL_FIELD), self.table.item(row, COL_EXAMPLE)
            if field_item is None or example is None:
                continue
            unmapped = combo.currentIndex() == 0
            mapped += not unmapped
            field_item.setBackground(UNMAPPED_BG if unmapped else QColor(0, 0, 0, 0))
            field_item.setToolTip(
                field_item.toolTip().split("\n⚠")[0]
                + ("\n⚠ Chưa ghép cột — trường này sẽ bị bỏ trống" if unmapped else "")
            )
            column = combo.currentData()
            sample = next(iter(self._samples.get(column, [])), "") if column else ""
            example.setForeground(QColor("#147253"))
            if not column:
                example.setText("")
                continue
            try:
                specs = [t.strip() for t in tr.text().split(";") if t.strip()]
                example.setText(apply_transforms(sample, specs) if sample else "(trống)")
            except Exception as e:
                example.setForeground(QColor("#b42338"))
                example.setText(f"⚠ {e}")
            example.setToolTip(f"Giá trị gốc: {sample}\nSau biến đổi: {example.text()}")
        total = len(self._editors)
        if total:
            set_message(
                self.mapped_info,
                f"Đã ghép {mapped}/{total} trường"
                + (f" • {total - mapped} trường chưa ghép (tô vàng)" if mapped < total else " ✔"),
                "hint" if mapped < total else "ok",
            )

    def _auto_suggest(self) -> None:
        if not self.state.profile:
            return
        suggestions = suggest_mapping(self.state.columns, self.state.profile)
        for name, (combo, _req, tr) in self._editors.items():
            if name in suggestions and not (
                self._base_mapping
                and any(
                    fm.field == name and fm.const is not None for fm in self._base_mapping.fields
                )
            ):
                combo.setCurrentIndex(combo.findData(suggestions[name]))
                if tr.text().strip() in {"", "strip"}:
                    spec = self.state.profile.fields[name]
                    tr.setText(
                        "; ".join(
                            suggest_transforms(
                                self._samples.get(suggestions[name], []), name, spec.label
                            )
                        )
                    )
        set_message(
            self.profile_hint,
            f"Đã tự ghép {len(suggestions)}/{len(self._editors)} trường theo tên cột — "
            "hãy kiểm tra lại, đặc biệt cột “Biến đổi”.",
        )

    # ── validation preview ──
    def _validate(self) -> None:
        self.state.validated = False
        self._validation_requested = False
        if self._task:
            self._task.cancel()
        problems = self.state.mapping_problems()
        mapper = self.state.mapper()
        if problems or not mapper or not self.state.mapping or not self.state.records:
            self.preview_model.set_data([], [])
            self.state.validation_pending = self.is_busy
            set_message(
                self.summary, "✖ " + " • ".join(problems or ["Chưa có dữ liệu nguồn"]), "error"
            )
            self.complete_changed.emit()
            return
        self.state.validation_pending = True
        self._validation_requested = True
        set_message(self.summary, f"Đang kiểm tra {len(self.state.records):,} dòng…")
        if not self._task:
            self._start_validation()
        self.complete_changed.emit()

    def _start_validation(self) -> None:
        assert self.state.mapping is not None and self.state.profile is not None
        mapper = Mapper(
            self.state.mapping.model_copy(deep=True), self.state.profile.model_copy(deep=True)
        )
        records = self.state.records
        self._validation_requested = False
        self._task = BackgroundTask(
            lambda control: validate_records(mapper, records, control), self
        )
        self._task.result.connect(self._validated_result)
        self._task.failed.connect(self._validation_failed)
        self._task.finished.connect(self._validation_finished)
        self._task.start()

    def _validated_result(self, value: object) -> None:
        assert isinstance(value, ValidationResult)
        profile = self.state.profile
        headers = {n: s.label or n for n, s in profile.fields.items()} if profile else {}
        self.preview_model.set_data(value.columns, value.rows, headers)
        for index, msg in value.errors:
            self.preview_model.set_status(index, RowStatus.INVALID, msg)
        self.state.validated = True
        if value.invalid_count:
            more = "…" if value.invalid_count > len(value.first_invalid) else ""
            first = ", ".join(map(str, value.first_invalid)) + more
            set_message(
                self.summary,
                f"⚠ {value.invalid_count}/{value.total} dòng dữ liệu lỗi (dòng {first}) — xem cột "
                "Ghi chú. Các dòng này sẽ được bỏ qua khi chạy; sửa file nguồn rồi mở lại "
                "nếu cần nhập chúng.",
                "error",
            )
        else:
            set_message(self.summary, f"✔ Tất cả {value.total:,} dòng hợp lệ.", "ok")
        self._remember()

    def _remember(self) -> None:
        """Next file with the same layout opens with the same settings (never edits YAML)."""
        mapping, source = self.state.mapping, self.state.source
        if not mapping or not source:
            return
        self._memory.remember_mapping(self.state.columns, mapping.profile, mapping)
        if isinstance(source, ExcelSource):
            self._memory.remember_source(self.state.sheets, source.options)

    def _validation_failed(self, message: str) -> None:
        self.state.validated = False
        set_message(self.summary, f"✖ {message}", "error")

    def _validation_finished(self) -> None:
        assert self._task is not None
        self._task.deleteLater()
        self._task = None
        if self._validation_requested:
            self._start_validation()
        else:
            self.state.validation_pending = self._debounce.isActive()
        self.complete_changed.emit()

    # ── persistence ──
    def _open_mapping(self) -> None:
        directory = get_settings().mappings_path
        directory.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(
            self, "Mở cấu hình ghép cột", str(directory), "YAML (*.yaml *.yml)"
        )
        if not path:
            return
        try:
            mapping = load_mapping(Path(path))
            idx = self.profile_box.findData(mapping.profile)
            if idx < 0:
                raise AutoInputError(f"Không tìm thấy ứng dụng đích '{mapping.profile}'")
            self.profile_box.blockSignals(True)
            self.profile_box.setCurrentIndex(idx)
            self.profile_box.blockSignals(False)
            self._fill_table(load_profile(self._profiles[mapping.profile]), mapping)
            self.source_options_requested.emit(mapping.source_options)
            set_message(self.profile_hint, f"✔ Đã mở cấu hình “{Path(path).name}”.", "ok")
        except AutoInputError as e:
            set_message(self.profile_hint, f"✖ {e.message}", "error")

    def _save_mapping(self) -> None:
        self.flush_edits()
        problems = self.state.mapping_problems()
        if problems:
            set_message(self.profile_hint, "✖ " + " • ".join(problems), "error")
            return
        if not self.state.mapping:
            return
        default = get_settings().mappings_path / f"{self.state.mapping.profile}.yaml"
        default.parent.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu cấu hình ghép cột", str(default), "YAML (*.yaml)"
        )
        if path:
            save_mapping(self.state.mapping, Path(path))
            set_message(
                self.profile_hint,
                f"✔ Đã lưu “{Path(path).name}” — lần sau chọn ứng dụng này sẽ tự nạp lại.",
                "ok",
            )


def _centered(child: QWidget) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(child)
    return box


def _short(text: str, limit: int = 24) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _with_presets(editor: QLineEdit) -> QWidget:
    """Transform editor plus a "+" menu of common Vietnamese presets."""
    button = QToolButton()
    button.setIcon(icon("plus"))
    button.setToolTip("Thêm phép biến đổi có sẵn")
    button.setAccessibleName("Thêm phép biến đổi")
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu = QMenu(button)
    for label, spec in TRANSFORM_PRESETS:
        action = menu.addAction(f"{label}    ({spec})")
        action.triggered.connect(
            lambda _=False, spec=spec: editor.setText(
                "; ".join([t for t in (x.strip() for x in editor.text().split(";")) if t] + [spec])
            )
        )
    menu.addSeparator()
    menu.addAction("Xoá hết biến đổi").triggered.connect(lambda: editor.setText(""))
    button.setMenu(menu)
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(editor, 1)
    layout.addWidget(button)
    box.setFocusProxy(editor)
    return box

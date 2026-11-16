from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTableWidget,
    QWidget,
)

from autoinput.domain import AutoInputError, FieldMap, Mapping, Profile, Record, RowStatus
from autoinput.infra.settings import get_settings
from autoinput.infra.storage import list_profiles, load_mapping, load_profile, save_mapping
from autoinput.mapping import suggest_mapping
from autoinput.transforms import transform_registry
from autoinput.ui.pages.base import WizardPage, message_label, set_message
from autoinput.ui.state import AppState
from autoinput.ui.widgets.records_model import RecordsModel

UNUSED = "— không dùng —"
PREVIEW_ROWS = 200
COL_FIELD, COL_SOURCE, COL_REQUIRED, COL_TRANSFORMS = range(4)


class MappingPage(WizardPage):
    title = "2. Ánh xạ cột → ứng dụng đích & kiểm tra"

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self._profiles: dict[str, Path] = {}
        self._debounce = QTimer(self, singleShot=True, interval=300)
        self._debounce.timeout.connect(self._rebuild_mapping)

        self.profile_box = QComboBox()
        self.profile_box.setMinimumWidth(260)
        self.profile_box.currentIndexChanged.connect(self._on_profile_changed)
        suggest = QPushButton("✨ Gợi ý tự động")
        suggest.clicked.connect(self._auto_suggest)
        open_btn = QPushButton("Mở mapping…")
        open_btn.clicked.connect(self._open_mapping)
        save_btn = QPushButton("Lưu mapping…")
        save_btn.clicked.connect(self._save_mapping)
        bar = QHBoxLayout()
        for w in (self.profile_box, suggest, open_btn, save_btn):
            bar.addWidget(w)
        bar.addStretch()

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Trường đích", "Cột nguồn", "Bắt buộc", "Biến đổi"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()

        self.summary = message_label()
        self.preview_model = RecordsModel(with_status=True)
        preview = QTableView()
        preview.setModel(self.preview_model)
        preview.horizontalHeader().setStretchLastSection(True)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table)
        split.addWidget(preview)
        self.root.addLayout(bar)
        self.root.addWidget(split, 1)
        self.root.addWidget(self.summary)

        self._reload_profiles()

    # ── lifecycle ──
    def on_enter(self) -> None:
        if self.state.profile:
            self._fill_table(self.state.profile, self.state.mapping)

    def is_complete(self) -> bool:
        return self.state.mapper() is not None

    # ── profiles ──
    def _reload_profiles(self) -> None:
        self._profiles = list_profiles(get_settings().profiles_dir)
        self.profile_box.clear()
        self.profile_box.addItem("Chọn ứng dụng đích…", None)
        for pid, path in self._profiles.items():
            self.profile_box.addItem(load_profile(path).name, pid)

    def _on_profile_changed(self) -> None:
        pid = self.profile_box.currentData()
        profile = load_profile(self._profiles[pid]) if pid else None
        if profile:
            self._fill_table(profile, None)
            self._auto_suggest()
        else:
            self.table.setRowCount(0)
            self.state.set_mapping(None, None)
            self._validate()

    # ── table <-> Mapping ──
    def _fill_table(self, profile: Profile, mapping: Mapping | None) -> None:
        existing = {fm.field: fm for fm in mapping.fields} if mapping else {}
        self.table.setRowCount(len(profile.fields))
        tooltip = "Phân tách bằng ';'. Có sẵn: " + ", ".join(transform_registry.keys())
        for row, (name, spec) in enumerate(profile.fields.items()):
            fm = existing.get(name)
            item_label = spec.label or name
            self.table.setCellWidget(
                row, COL_FIELD, _readonly(item_label + (" 🔒" if spec.sensitive else ""), name)
            )

            combo = QComboBox()
            combo.addItems([UNUSED, *self.state.columns])
            if fm and fm.source in self.state.columns:
                combo.setCurrentText(fm.source)
            combo.currentIndexChanged.connect(self._debounce.start)
            self.table.setCellWidget(row, COL_SOURCE, combo)

            req = QCheckBox()
            req.setChecked(bool(fm and fm.required))
            req.toggled.connect(self._debounce.start)
            self.table.setCellWidget(row, COL_REQUIRED, _centered(req))

            tr = QLineEdit("; ".join(fm.transforms) if fm else "strip")
            tr.setToolTip(tooltip)
            tr.setPlaceholderText("vd: strip; title; date:%d/%m/%Y")
            tr.textChanged.connect(self._debounce.start)
            self.table.setCellWidget(row, COL_TRANSFORMS, tr)
        self.state.profile = profile
        self._rebuild_mapping()

    def _rebuild_mapping(self) -> None:
        profile = self.state.profile
        if not profile:
            return
        fields: list[FieldMap] = []
        for row in range(self.table.rowCount()):
            name = self.table.cellWidget(row, COL_FIELD).property("field")
            source = self.table.cellWidget(row, COL_SOURCE).currentText()
            if source == UNUSED:
                continue
            required = self.table.cellWidget(row, COL_REQUIRED).findChild(QCheckBox).isChecked()
            text = self.table.cellWidget(row, COL_TRANSFORMS).text()
            transforms = [t.strip() for t in text.split(";") if t.strip()]
            fields.append(
                FieldMap(field=name, source=source, required=required, transforms=transforms)
            )
        options = self.state.source.options if self.state.source else None
        mapping = Mapping(
            name=self.state.mapping.name if self.state.mapping else profile.name,
            profile=profile.id,
            fields=fields,
            **({"source_options": options} if options else {}),
        )
        self.state.set_mapping(profile, mapping)
        self._validate()

    def _auto_suggest(self) -> None:
        if not self.state.profile:
            return
        suggestions = suggest_mapping(self.state.columns, self.state.profile)
        for row in range(self.table.rowCount()):
            name = self.table.cellWidget(row, COL_FIELD).property("field")
            if name in suggestions:
                self.table.cellWidget(row, COL_SOURCE).setCurrentText(suggestions[name])
        set_message(
            self.summary,
            f"Đã gợi ý {len(suggestions)}/{self.table.rowCount()} trường — hãy kiểm tra lại.",
        )

    # ── validation preview ──
    def _validate(self) -> None:
        problems = self.state.mapping_problems()
        mapper = self.state.mapper()
        if problems or not mapper or not self.state.mapping:
            self.preview_model.set_data([], [])
            set_message(self.summary, "✖ " + " • ".join(problems), "error")
            self.complete_changed.emit()
            return

        cols = [fm.field for fm in self.state.mapping.fields]
        rows: list[Record] = []
        invalid: list[tuple[int, str]] = []
        for item in mapper.apply_all(self.state.records):
            if len(rows) < PREVIEW_ROWS:
                rows.append(Record(item.record.index, {**item.values, **item.errors}))
            if not item.ok:
                invalid.append(
                    (item.record.index, "; ".join(f"{k}: {v}" for k, v in item.errors.items()))
                )
        self.preview_model.set_data(cols, rows)
        for index, msg in invalid:
            self.preview_model.set_status(index, RowStatus.INVALID, msg)

        if invalid:
            first = ", ".join(str(i) for i, _ in invalid[:10])
            set_message(
                self.summary,
                f"⚠ {len(invalid)}/{len(self.state.records)} dòng dữ liệu lỗi (dòng {first}…) — "
                "các dòng này sẽ bị bỏ qua khi chạy.",
                "error",
            )
        else:
            set_message(self.summary, f"✔ Tất cả {len(self.state.records)} dòng hợp lệ.", "ok")
        self.complete_changed.emit()

    # ── persistence ──
    def _open_mapping(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Mở mapping", str(get_settings().mappings_dir), "YAML (*.yaml *.yml)"
        )
        if not path:
            return
        try:
            mapping = load_mapping(Path(path))
            idx = self.profile_box.findData(mapping.profile)
            if idx < 0:
                raise AutoInputError(f"Không tìm thấy profile '{mapping.profile}'")
            self.profile_box.blockSignals(True)
            self.profile_box.setCurrentIndex(idx)
            self.profile_box.blockSignals(False)
            self._fill_table(load_profile(self._profiles[mapping.profile]), mapping)
        except AutoInputError as e:
            set_message(self.summary, f"✖ {e.message}", "error")

    def _save_mapping(self) -> None:
        if not self.state.mapping:
            return
        default = get_settings().mappings_dir / f"{self.state.mapping.profile}.yaml"
        path, _ = QFileDialog.getSaveFileName(self, "Lưu mapping", str(default), "YAML (*.yaml)")
        if path:
            save_mapping(self.state.mapping, Path(path))
            set_message(self.summary, f"✔ Đã lưu {Path(path).name}", "ok")


def _readonly(text: str, field: str) -> QLineEdit:
    w = QLineEdit(text)
    w.setReadOnly(True)
    w.setFrame(False)
    w.setProperty("field", field)
    return w


def _centered(child: QWidget) -> QWidget:
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(child)
    return box

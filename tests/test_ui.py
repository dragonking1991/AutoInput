from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton

from autoinput.ui.main_window import MainWindow
from autoinput.ui.theme import apply_theme


def wait_until(predicate: Callable[[], bool], timeout: int = 5000) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    if predicate():
        return
    loop = QEventLoop()
    poll = QTimer(loop)
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer(loop)
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll.start()
    deadline.start(timeout)
    loop.exec()
    assert predicate(), "Background operation did not finish"


def load_demo(window: MainWindow, samples: Path) -> None:
    from autoinput.infra.storage import load_mapping, load_profile

    window.source_page._open(samples / "customers.csv")
    wait_until(window.source_page.is_complete)
    window.nav.setCurrentRow(1)
    window.mapping_page._fill_table(
        load_profile(samples.parent / "profiles/demo_web_form.yaml"),
        load_mapping(samples.parent / "mappings/demo_web_form.yaml"),
    )
    wait_until(window.mapping_page.is_complete)


@pytest.fixture
def application(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    return app


@pytest.fixture
def window(application):
    view = MainWindow()
    view.show()
    application.processEvents()
    yield view
    view.source_page.cancel()
    view.mapping_page.cancel()
    view.run_page.stop()
    wait_until(
        lambda: (
            not (view.source_page.is_busy or view.mapping_page.is_busy or view.run_page.is_running)
        )
    )
    view.close()
    application.processEvents()


@pytest.mark.parametrize("size", [(900, 640), (1280, 800)])
def test_controls_fit_without_horizontal_page_scrolling(application, window, size, samples: Path):
    load_demo(window, samples)
    window.resize(*size)

    for step in range(3):
        window.nav.setCurrentRow(step)
        wait_until(lambda: not window.state.validation_pending)
        application.processEvents()
        assert window.stack.currentIndex() == step
        scroll = window.stack.widget(step)
        assert scroll.horizontalScrollBar().maximum() == 0
        for kind in (QPushButton, QCheckBox):
            for control in window.pages[step].findChildren(kind):
                if control.isVisible():
                    assert control.width() >= control.sizeHint().width(), control.text()
                    assert control.height() >= control.sizeHint().height(), control.text()

    assert window.mapping_page.table.verticalHeader().defaultSectionSize() >= (
        window.mapping_page.table.cellWidget(0, 1).sizeHint().height()
    )
    assert window.run_page.dry_run.isChecked()


def test_log_toggle_keeps_preview_space(application, window):
    assert not window.log_dock.isVisible()
    window.log_btn.click()
    application.processEvents()
    assert window.log_dock.isVisible()
    window.log_dock.close()
    application.processEvents()
    assert not window.log_btn.isChecked()


def test_drop_zone_accepts_keyboard_selection(application, window, monkeypatch):
    from PySide6.QtTest import QTest

    opened = []
    monkeypatch.setattr(window.source_page.drop, "browse", lambda: opened.append(True))
    window.source_page.drop.setFocus()
    QTest.keyClick(window.source_page.drop, Qt.Key.Key_Return)
    assert opened == [True]


def test_dry_run_updates_results_and_unlocks_controls(application, window, samples: Path):
    from autoinput.domain import RowStatus

    load_demo(window, samples)
    window.nav.setCurrentRow(2)
    window.run_page.delay.setValue(0)
    window.run_page.start()
    wait_until(lambda: not window.run_page.is_running)
    assert not window.run_page.is_running
    report = window.run_page._report
    assert report is not None
    assert report.count(RowStatus.DONE) == 2
    assert report.count(RowStatus.INVALID) == 1
    assert window.run_page.start_btn.isEnabled()
    assert window.run_page.export_btn.isEnabled()
    assert window.back_btn.isEnabled()
    # Dry-run must never read as if data was entered.
    assert window.run_page.model.data(window.run_page.model.index(0, 0)) == "Đã chạy thử"
    assert "Chưa có gì được nhập" in window.run_page.summary.text()
    # Invalid data rows are not "retryable": re-running them without fixing the file is pointless.
    assert not window.run_page.retry_btn.isEnabled()
    window.source_page._open(samples / "customers.json")
    assert window.run_page._report is None
    assert not window.run_page.retry_btn.isEnabled()
    assert not window.run_page.export_btn.isEnabled()


def test_selecting_target_reuses_saved_mapping_rules(window, samples):
    window.source_page._open(samples / "customers.csv")
    wait_until(window.source_page.is_complete)
    window.nav.setCurrentRow(1)
    box = window.mapping_page.profile_box
    box.setCurrentIndex(box.findData("demo_web_form"))
    wait_until(window.mapping_page.is_complete)
    # The saved mapping validates dates/phones, so the bad sample row 3 must be flagged.
    assert "demo_web_form.yaml" in window.mapping_page.profile_hint.text()
    assert "1/3 dòng dữ liệu lỗi" in window.mapping_page.summary.text()
    model = window.mapping_page.preview_model
    assert model.headerData(2, Qt.Orientation.Horizontal) == "Họ và tên"
    assert model.data(model.index(0, 0)) == "Hợp lệ"


def test_live_run_requires_confirmation(window, samples, monkeypatch):
    load_demo(window, samples)
    window.nav.setCurrentRow(2)
    window.run_page.dry_run.setChecked(False)
    assert window.run_page.start_btn.text().startswith("Nhập thật")
    asked = []
    monkeypatch.setattr(window.run_page, "_confirm_live", lambda n: asked.append(n) or False)
    window.run_page.start()
    assert asked == [3]
    assert not window.run_page.is_running


@pytest.mark.parametrize("row_count", [2, 3])
def test_source_limit_is_reported_without_partial_data(window, tmp_path, monkeypatch, row_count):
    import autoinput.ui.state as state_module

    monkeypatch.setattr(state_module, "MAX_ROWS_IN_MEMORY", 2)
    path = tmp_path / "limit.csv"
    path.write_text("Name\n" + "".join(f"Row {i}\n" for i in range(row_count)), encoding="utf-8")
    window.source_page._open(path)
    wait_until(lambda: not window.source_page.is_busy)
    if row_count == 2:
        assert len(window.state.records) == 2
        assert window.source_page.is_complete()
        return
    assert window.state.records == []
    assert window.state.source is None
    assert "vượt giới hạn" in window.source_page.info.text()
    assert not window.source_page.is_complete()


def test_source_loading_is_responsive_and_discards_superseded_request(window, samples, monkeypatch):
    import threading

    from PySide6.QtCore import QTimer

    import autoinput.ui.pages.source_page as module

    entered, release = threading.Event(), threading.Event()
    read_source = module.read_source

    def blocked_read(path, options, control, auto="off"):
        entered.set()
        while not release.wait(0.01):
            control.checkpoint()
        return read_source(path, options, control, auto)

    monkeypatch.setattr(module, "read_source", blocked_read)
    window.source_page._open(samples / "customers.csv")
    wait_until(entered.is_set)
    heartbeat = []
    QTimer.singleShot(0, lambda: heartbeat.append(True))
    wait_until(lambda: bool(heartbeat))
    assert window.state.source_busy
    assert not window.next_btn.isEnabled()
    window.source_page._open(samples / "customers.json")
    release.set()
    wait_until(window.source_page.is_complete)
    assert window.state.source.path.name == "customers.json"


def test_excel_view_detects_table_and_edits_rows_from_menu(window, merged_workbook, samples):
    page = window.source_page
    page._open(merged_workbook)
    wait_until(lambda: not page.is_busy)
    assert page.is_complete(), page.info.text()
    assert "tự nhận diện" in page.info.text().lower()
    assert (page.header_row.value(), page.header_rows.value()) == (4, 2)
    assert page.smart_rows.isChecked() and page.display_values.isChecked()
    sheet = page.sheet_model
    assert page.current_table is page.sheet_view
    assert sheet.headerData(1, Qt.Orientation.Horizontal) == "B"
    assert sheet.headerData(1, Qt.Orientation.Vertical) == "2"
    assert sheet.data(sheet.index(1, 1)) == "Report"
    assert page.sheet_view.columnSpan(1, 1) == 3
    assert page.sheet_view.rowSpan(3, 1) == 2
    assert sheet.role_of(3)[0] == "header"
    assert sheet.headerData(5, Qt.Orientation.Vertical, Qt.ItemDataRole.DecorationRole)
    assert "Income / Base" in window.state.columns
    first = window.state.records[0]
    assert (first.index, first.data["Income / Base"]) == (6, "10")
    assert "tiêu đề dòng 4–5" in page.layout_summary.text()

    menu = page.row_menu(5)
    skip = next(a for a in menu.actions() if a.text() == "Bỏ qua dòng 6")
    skip.trigger()
    wait_until(lambda: not page.is_busy)
    assert 6 not in [r.index for r in window.state.records]
    assert sheet.role_of(5) == ("skip", "bạn chọn bỏ qua")
    assert any(a.text() == "Nhập lại dòng 6" for a in page.row_menu(5).actions())

    records = window.state.records
    page.preview_mode.setCurrentIndex(1)
    assert page.current_table is page.table
    assert page.model.headerData(2, Qt.Orientation.Horizontal) == "Income / Base"
    assert window.state.records is records
    page.preview_mode.setCurrentIndex(0)
    page._open(samples / "customers.csv")
    wait_until(lambda: not page.is_busy)
    assert page.is_complete(), page.info.text()
    assert page.current_table is page.table
    assert not page.preview_mode.isVisible()
    assert page.model.headerData(0, Qt.Orientation.Horizontal) == "Họ và Tên"


def test_header_row_has_padding_and_no_buttons_and_commits_typed_value(window, application):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox

    field = window.source_page.header_row
    field.setFocus()
    application.processEvents()
    editor = field.lineEdit()
    assert editor.geometry().width() > 50
    assert editor.geometry().left() + editor.textMargins().left() >= 8
    assert field.width() - editor.geometry().right() + editor.textMargins().right() >= 8
    option = QStyleOptionSpinBox()
    field.initStyleOption(option)
    for subcontrol in (QStyle.SubControl.SC_SpinBoxUp, QStyle.SubControl.SC_SpinBoxDown):
        rect = field.style().subControlRect(
            QStyle.ComplexControl.CC_SpinBox, option, subcontrol, field
        )
        assert rect.isEmpty()
    changes = []
    field.valueChanged.connect(changes.append)
    field.selectAll()
    QTest.keyClicks(field, "12")
    assert changes == []
    QTest.keyClick(field, Qt.Key.Key_Return)
    assert field.value() == 12
    assert changes == [12]


def test_multiple_sheets_have_explicit_picker_and_switch_source(window, merged_workbook, samples):
    from PySide6.QtTest import QTest

    page = window.source_page
    page.sheet.addItem("Only")
    page._update_sheet_hint()
    assert page.sheet_label.text() == "Sheet (1):"
    assert page.sheet_button.isHidden()
    page._open(merged_workbook)
    wait_until(lambda: not page.is_busy)
    assert page.is_complete(), page.info.text()
    assert page.sheet_label.text() == "Sheet (2):"
    assert page.sheet_button.isVisible()
    assert "2 sheet" in page.sheet.toolTip()
    QTest.mouseClick(page.sheet_button, Qt.MouseButton.LeftButton)
    assert page.sheet.view().isVisible()
    QTest.keyClick(page.sheet, Qt.Key.Key_Down)
    QTest.keyClick(page.sheet, Qt.Key.Key_Return)
    wait_until(lambda: not page.is_busy)
    assert page.is_complete(), page.info.text()
    assert page.sheet.currentText() == "Other"
    assert window.state.columns == ["Code"]
    assert window.state.records[0].data["Code"] == "Example"
    page._open(samples / "customers.csv")
    wait_until(lambda: not page.is_busy)
    assert page.sheet_field.isHidden()
    assert page.sheet_button.isHidden()


def test_mapping_preserves_constant_default_and_source_options(window, samples):
    from autoinput.domain import FieldMap, Mapping, SourceOptions
    from autoinput.infra.storage import load_profile

    window.source_page._open(samples / "customers.csv")
    wait_until(window.source_page.is_complete)
    profile = load_profile(samples.parent / "profiles/demo_web_form.yaml")
    mapping = Mapping(
        name="Preserved",
        profile=profile.id,
        source_options=SourceOptions(record_path="data.items", encoding="utf-8", delimiter=";"),
        fields=[
            FieldMap(
                field="phone",
                source="Điện Thoại",
                const="0912345678",
                default="fallback",
                required=True,
            ),
            FieldMap(field="full_name", default="Unknown"),
        ],
    )
    window.mapping_page._fill_table(profile, mapping)
    wait_until(window.mapping_page.is_complete)
    result = window.state.mapping
    assert result.name == mapping.name
    assert result.source_options == mapping.source_options
    assert {fm.field: fm for fm in result.fields} == {fm.field: fm for fm in mapping.fields}


def test_validation_is_background_and_pending_edits_block_run(window, samples, monkeypatch):
    import threading

    from PySide6.QtCore import QTimer

    import autoinput.ui.pages.mapping_page as module

    load_demo(window, samples)
    entered, release = threading.Event(), threading.Event()
    validate = module.validate_records

    def blocked_validate(mapper, records, control):
        entered.set()
        while not release.wait(0.01):
            control.checkpoint()
        return validate(mapper, records, control)

    monkeypatch.setattr(module, "validate_records", blocked_validate)
    editor = window.mapping_page._editors["full_name"][2]
    editor.setText("upper")
    assert window.state.validation_pending
    window.run_page.start()
    assert not window.run_page.is_running
    window.mapping_page.flush_edits()
    wait_until(entered.is_set)
    heartbeat = []
    QTimer.singleShot(0, lambda: heartbeat.append(True))
    wait_until(lambda: bool(heartbeat))
    assert not window.mapping_page.is_complete()
    editor.setText("lower")
    window.mapping_page.flush_edits()
    release.set()
    wait_until(window.mapping_page.is_complete)
    assert window.state.mapping.fields[0].transforms == ["lower"]
    assert (
        window.mapping_page.preview_model.data(window.mapping_page.preview_model.index(0, 2))
        == "nguyễn  văn an"
    )


def test_close_waits_for_running_thread(window, samples, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QMessageBox

    load_demo(window, samples)
    window.nav.setCurrentRow(2)
    window.run_page.step_mode.setChecked(True)
    window.run_page.start()
    assert window.run_page.is_running
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert window.isVisible()
    wait_until(lambda: not window.isVisible())
    assert not window.run_page.is_running


def test_open_mapping_reloads_source_options(window, samples, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from autoinput.domain import FieldMap, Mapping, SourceOptions
    from autoinput.infra.storage import save_mapping

    data = tmp_path / "nested.json"
    data.write_text('{"data":{"items":[{"name":"Alice"},{"name":"Bob"}]}}', encoding="utf-8")
    window.source_page._open(data)
    wait_until(window.source_page.is_complete)
    mapping = Mapping(
        name="Nested JSON",
        profile="demo_web_form",
        source_options=SourceOptions(record_path="data.items"),
        fields=[FieldMap(field="full_name", source="name", default="Unknown")],
    )
    path = tmp_path / "mapping.yaml"
    save_mapping(mapping, path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(path), "YAML"))
    window.mapping_page._open_mapping()
    wait_until(window.mapping_page.is_complete)
    assert window.state.source.options == mapping.source_options
    assert [r.data["name"] for r in window.state.records] == ["Alice", "Bob"]
    assert window.state.mapping == mapping


def test_close_waits_for_source_worker(window, samples, monkeypatch):
    import threading

    from PySide6.QtGui import QCloseEvent

    import autoinput.ui.pages.source_page as module

    entered, release = threading.Event(), threading.Event()
    read_source = module.read_source

    def blocked_read(path, options, control, auto="off"):
        entered.set()
        while not release.wait(0.01):
            control.checkpoint()
        return read_source(path, options, control, auto)

    monkeypatch.setattr(module, "read_source", blocked_read)
    window.source_page._open(samples / "customers.csv")
    wait_until(entered.is_set)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    release.set()
    wait_until(lambda: not window.isVisible())
    assert not window.source_page.is_busy


def test_mapping_shows_samples_examples_presets_and_remembers(window, samples):
    from PySide6.QtWidgets import QToolButton

    from autoinput.ui.pages.mapping_page import COL_EXAMPLE, COL_TRANSFORMS

    window.source_page._open(samples / "customers.csv")
    wait_until(window.source_page.is_complete)
    window.nav.setCurrentRow(1)
    page = window.mapping_page
    page.profile_box.setCurrentIndex(page.profile_box.findData("demo_web_form"))
    wait_until(page.is_complete)
    name, (combo, _req, editor) = next(
        (n, e) for n, e in page._editors.items() if e[0].currentIndex() > 0
    )
    assert "vd:" in combo.currentText()
    assert "Đã ghép" in page.mapped_info.text()
    row = list(page._editors).index(name)
    assert page.table.item(row, COL_EXAMPLE).text()

    button = page.table.cellWidget(row, COL_TRANSFORMS).findChild(QToolButton)
    upper = next(a for a in button.menu().actions() if a.text().endswith("(upper)"))
    upper.trigger()
    assert editor.text().split("; ")[-1] == "upper"
    page.flush_edits()
    wait_until(page.is_complete)
    assert page.table.item(row, COL_EXAMPLE).text().isupper()

    # Same columns again: the remembered target and rules come back without any clicks.
    page.profile_box.setCurrentIndex(0)
    window.nav.setCurrentRow(0)
    window.source_page._open(samples / "customers.csv")
    wait_until(window.source_page.is_complete)
    wait_until(lambda: page.profile_box.currentData() == "demo_web_form")
    assert page._editors[name][2].text().split("; ")[-1] == "upper"
    assert "đã nhớ" in page.profile_hint.text()

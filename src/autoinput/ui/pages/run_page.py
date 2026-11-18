import sys
from collections.abc import Callable
from pathlib import Path
from time import monotonic

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
)

from autoinput.core.rows import parse_rows
from autoinput.domain import AutoInputError, RowStatus, RunOptions, RunReport
from autoinput.engine import Journal, RunControl, RunEvent, Runner, start_kill_switch
from autoinput.infra.settings import get_settings
from autoinput.ui.icons import IconName, icon
from autoinput.ui.pages.base import WizardPage, configure_table, message_label, set_message
from autoinput.ui.state import AppState
from autoinput.ui.theme import STATUS_COLORS
from autoinput.ui.widgets.records_model import RecordsModel
from autoinput.ui.worker import RunWorker, start_worker


class RunPage(WizardPage):
    title = "3. Chạy nhập liệu"
    description = (
        "Chạy thử trước, kiểm tra kết quả rồi mới nhập thật. Bạn có thể dừng bất cứ lúc nào."
    )

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self.settings = get_settings()
        self.journal = Journal(self.settings.journal_path)
        self._control: RunControl | None = None
        self._thread: QThread | None = None
        self._worker: RunWorker | None = None
        self._stop_hotkey: Callable[[], None] = lambda: None
        self._report: RunReport | None = None
        self._dry_run = True
        self._last_scroll = 0.0

        # ── options ──
        self.dry_run = QCheckBox("Chạy thử (không nhập thật)")
        self.dry_run.setChecked(True)
        self.dry_run.setToolTip(
            "Chỉ đi qua kịch bản và ghi log, không mở/điều khiển ứng dụng đích. "
            "Bỏ chọn để nhập thật."
        )
        self.step_mode = QCheckBox("Từng dòng")
        self.step_mode.setToolTip(
            f"Dừng sau mỗi dòng; bấm “Dòng tiếp” ({_label('step')}) để nhập dòng kế tiếp."
        )
        self.stop_on_error = QCheckBox("Dừng khi gặp lỗi")
        self.rows = QLineEdit()
        self.rows.setPlaceholderText("Tất cả — hoặc vd: 1-10, 15")
        self.delay = QDoubleSpinBox(
            minimum=0, maximum=10, singleStep=0.1, value=0.3, suffix=" giây"
        )
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.addRow(self.dry_run)
        form.addRow(self.step_mode)
        form.addRow(self.stop_on_error)
        form.addRow("Chỉ các dòng:", self.rows)
        form.addRow("Nghỉ giữa các dòng:", self.delay)
        opts = QGroupBox("Tuỳ chọn")
        opts.setLayout(form)
        self.mode_hint = message_label()

        # ── controls ──
        self.start_btn = _button("", "primary", self.start, "play")
        self.pause_btn = _button(f"Tạm dừng ({_label('pause')})", "", self.toggle_pause, "pause")
        self.step_btn = _button(f"Dòng tiếp ({_label('step')})", "", self.step, "next")
        self.stop_btn = _button(f"Dừng ({_label('stop')})", "danger", self.stop, "stop")
        self.retry_btn = _button("Chạy lại dòng lỗi", "", self.retry_failed, "retry")
        self.retry_btn.setToolTip(
            "Chỉ chạy lại dòng thất bại trước khi kịp thao tác. Không gồm dòng dữ liệu lỗi "
            "(cần sửa file) và dòng cần đối soát (có thể đã lưu)."
        )
        self.export_btn = _button("Xuất báo cáo", "", self.export_report, "save")
        ctrl = QGridLayout()
        ctrl.setSpacing(8)
        for i, b in enumerate(
            (
                self.start_btn,
                self.pause_btn,
                self.step_btn,
                self.stop_btn,
                self.retry_btn,
                self.export_btn,
            )
        ):
            ctrl.addWidget(b, i // 2, i % 2)
        hint = QLabel(f"Dừng khẩn cấp bất kỳ lúc nào: {hotkey_label(self.settings.kill_switch)}")
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        self.countdown = QLabel()
        self.countdown.hide()
        self.countdown.setObjectName("countdown")
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.summary = message_label()
        self.summary.setText("Kiểm tra chế độ và phạm vi dòng, sau đó bấm Bắt đầu.")
        self.model = RecordsModel(with_status=True)
        self.table = QTableView()
        self.table.setModel(self.model)
        configure_table(self.table)

        top = QHBoxLayout()
        top.addWidget(opts, 2)
        top.addLayout(ctrl, 1)
        self.root.addLayout(top)
        self.root.addWidget(self.mode_hint)
        self.root.addWidget(hint)
        self.root.addWidget(self.countdown)
        self.root.addWidget(self.progress)
        self.root.addWidget(self.summary)
        self.root.addWidget(self.table, 1)

        actions = {
            "start": self.start,
            "pause": self.toggle_pause,
            "step": self.step,
            "stop": self.stop,
        }
        for name, slot in actions.items():
            for key in SHORTCUTS[name]:
                QShortcut(QKeySequence(key), self, slot)
        self._set_running(False)
        self.dry_run.toggled.connect(self._update_mode)
        self.step_mode.toggled.connect(self._update_mode)
        self._update_mode()
        self.state.source_changed.connect(self._invalidate_report)
        self.state.mapping_changed.connect(self._invalidate_report)

    def _update_mode(self) -> None:
        live = not self.dry_run.isChecked()
        self.start_btn.setText(f"{'Nhập thật' if live else 'Chạy thử'} ({_label('start')})")
        self.start_btn.setObjectName("danger" if live else "primary")
        self.start_btn.setIcon(icon("play", "#b42338" if live else "#ffffff"))
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        target = self.state.profile.name if self.state.profile else "ứng dụng đích"
        if live:
            set_message(
                self.mode_hint,
                f"⚠ Nhập thật: AutoInput sẽ điều khiển “{target}”. Nên chạy thử và bật "
                "“Từng dòng” cho vài dòng đầu.",
                "error",
            )
        else:
            set_message(
                self.mode_hint,
                "Chạy thử: kiểm tra dữ liệu và kịch bản, không thao tác lên ứng dụng đích. "
                "Bỏ chọn “Chạy thử” để nhập thật.",
            )
        if self.is_running:
            self.step_btn.setEnabled(self.step_mode.isChecked())

    def _invalidate_report(self) -> None:
        if not self.is_running:
            self._report = None
            self.retry_btn.setEnabled(False)
            self.export_btn.setEnabled(False)

    @property
    def is_running(self) -> bool:
        return self._control is not None

    def on_enter(self) -> None:
        self._update_mode()
        if not self.is_running:
            self.model.set_data(self.state.columns, self.state.records)

    # ── actions ──
    def start(self) -> None:
        if self.state.source_busy or self.state.validation_pending:
            set_message(self.summary, "Đang đọc/kiểm tra dữ liệu. Vui lòng đợi hoàn tất.", "error")
            return
        if not self.state.validated:
            set_message(
                self.summary,
                "Hãy quay lại bước ánh xạ và kiểm tra dữ liệu trước khi chạy.",
                "error",
            )
            return
        mapper = self.state.mapper()
        if self.is_running or not mapper or not self.state.profile:
            if not self.is_running:
                set_message(
                    self.summary, "Chưa có mapping hợp lệ. Hãy quay lại bước ánh xạ.", "error"
                )
            return
        try:
            options = RunOptions(
                dry_run=self.dry_run.isChecked(),
                step_mode=self.step_mode.isChecked(),
                stop_on_error=self.stop_on_error.isChecked(),
                rows=parse_rows(self.rows.text()),
                delay_between_records=self.delay.value(),
            )
        except ValueError:
            set_message(self.summary, "✖ Danh sách dòng không hợp lệ. Ví dụ: 1-10, 15", "error")
            return
        selected = sum(
            1 for r in self.state.records if options.rows is None or r.index in options.rows
        )
        if not selected:
            set_message(self.summary, "✖ Không có dòng nào khớp “Chỉ các dòng”.", "error")
            return
        if not options.dry_run and not self._confirm_live(selected):
            return

        self._control = RunControl()
        try:
            runner = Runner(
                self.state.profile, mapper, options, control=self._control, journal=self.journal
            )
        except AutoInputError as e:
            self._control = None
            set_message(self.summary, f"✖ {e.message}", "error")
            return

        self._report = None
        self._dry_run = options.dry_run
        self.model.set_data(self.state.columns, self.state.records)
        self.model.set_status_overrides(
            {"done": ("Đã chạy thử", STATUS_COLORS["done"])} if options.dry_run else {}
        )
        worker = RunWorker(
            runner, self.state.records, str(self.state.source.path if self.state.source else "")
        )
        worker.event_received.connect(self._on_event)
        worker.rows_received.connect(self._on_rows)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        if runner.driver.needs_focus:
            self._stop_hotkey = start_kill_switch(self.settings.kill_switch, self._control.cancel)
        self._thread = start_worker(worker)
        self._thread.finished.connect(self._on_done)
        self._set_running(True)

    def _confirm_live(self, selected: int) -> bool:
        assert self.state.profile is not None
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Xác nhận nhập thật")
        box.setText(f"Nhập thật tối đa {selected:,} dòng vào “{self.state.profile.name}”?")
        box.setInformativeText(
            "AutoInput sẽ điều khiển ứng dụng đích; dòng dữ liệu lỗi được bỏ qua. "
            + (
                "Trong lúc chạy, đừng dùng chuột/bàn phím. "
                f"Dừng khẩn cấp: {hotkey_label(self.settings.kill_switch)}."
                if self.state.profile.driver in {"mac", "uia"}
                else "Bạn vẫn có thể làm việc khác trong lúc chạy."
            )
        )
        go = box.addButton("Nhập thật", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Huỷ", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(QMessageBox.StandardButton.NoButton)
        box.exec()
        return box.clickedButton() is go

    def toggle_pause(self) -> None:
        if not self._control:
            return
        if self._control.is_paused:
            self._control.resume()
            self.pause_btn.setText(f"Tạm dừng ({_label('pause')})")
            self.pause_btn.setIcon(icon("pause"))
            set_message(self.summary, "Đang chạy…")
        else:
            self._control.pause()
            self.pause_btn.setText(f"Tiếp tục ({_label('pause')})")
            self.pause_btn.setIcon(icon("play"))
            set_message(self.summary, "⏸ Đã tạm dừng — sẽ dừng sau thao tác hiện tại.")

    def step(self) -> None:
        if self._control and self._control.is_paused:
            self._control.resume()

    def stop(self) -> None:
        if self._control:
            self._control.cancel()
            set_message(self.summary, "Đang dừng…")

    def retry_failed(self) -> None:
        if self._report and (rows := self._report.retryable_rows):
            self.rows.setText(",".join(map(str, sorted(rows))))
            self.start()

    def export_report(self) -> None:
        if not self._report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất báo cáo", f"report_{self._report.run_id}.csv", "CSV (*.csv)"
        )
        if path:
            self.journal.export_csv(self._report.run_id, Path(path))
            set_message(self.summary, f"✔ Đã xuất {Path(path).name}", "ok")

    # ── events from worker (already on GUI thread) ──
    def _on_failed(self, message: str) -> None:
        set_message(self.summary, f"✖ {message}", "error")

    def _on_rows(self, events: list[RunEvent]) -> None:
        for event in events:
            self._on_event(event)

    def _on_event(self, e: RunEvent) -> None:
        match e.kind:
            case "started":
                self.progress.setRange(0, max(e.total, 1))
                self.progress.setValue(0)
                verb = "chạy thử" if self._dry_run else "nhập"
                set_message(self.summary, f"Chuẩn bị {verb} {e.total:,} dòng…")
            case "countdown":
                self.countdown.show()
                self.countdown.setText(f"{e.message}")
                set_message(self.summary, "Chuyển sang ứng dụng đích ngay — bắt đầu sau…")
            case "row_started" if e.row is not None:
                self.countdown.clear()
                self.countdown.hide()
                self.model.set_status(e.row, RowStatus.RUNNING)
                if (
                    monotonic() - self._last_scroll >= 0.1
                    and (pos := self.model.position_of(e.row)) is not None
                ):
                    self.table.scrollTo(self.model.index(pos, 0))
                    self._last_scroll = monotonic()
            case "row_finished" if e.result:
                self.model.set_status(e.result.index, e.result.status, e.result.message)
                self.progress.setValue(e.position)
            case "paused":
                set_message(
                    self.summary,
                    f"⏸ Xong dòng {e.row}. Bấm {_label('step')} để nhập dòng tiếp theo.",
                )
            case "finished" if e.report:
                self._report = e.report
                r = e.report
                done, failed = r.count(RowStatus.DONE), r.count(RowStatus.FAILED)
                invalid, duration = r.count(RowStatus.INVALID), r.duration_seconds
                if self._dry_run:
                    head = "⏹ Đã dừng chạy thử" if r.cancelled else "✔ Chạy thử xong"
                    text = (
                        f"{head}: {done} dòng sẵn sàng • {failed} lỗi kịch bản • "
                        f"{invalid} dữ liệu lỗi • {duration:.1f}s. Chưa có gì được nhập — "
                        "bỏ chọn “Chạy thử” để nhập thật."
                    )
                else:
                    head = (
                        "⏹ Đã dừng"
                        if r.cancelled
                        else "⚠ Cần đối soát"
                        if r.review_rows
                        else "✔ Hoàn tất"
                    )
                    text = (
                        f"{head}: {done} đã nhập • {failed} thất bại • "
                        f"{invalid} dữ liệu lỗi • {duration:.1f}s"
                    )
                if r.review_rows:
                    text += (
                        f" • Cần đối soát dòng {','.join(map(str, sorted(r.review_rows)))} "
                        "(có thể đã lưu; kiểm tra trên ứng dụng đích trước khi nhập lại)"
                    )
                bad = failed or r.review_rows or r.cancelled
                set_message(self.summary, text, "error" if bad else "ok")

    def _on_done(self) -> None:
        self._stop_hotkey()
        self._stop_hotkey = lambda: None
        self._control = None
        self._thread = None
        self._worker = None
        self.countdown.clear()
        self.countdown.hide()
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        for w in (self.dry_run, self.step_mode, self.stop_on_error, self.rows, self.delay):
            w.setEnabled(not running)
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.step_btn.setEnabled(running and self.step_mode.isChecked())
        self.stop_btn.setEnabled(running)
        self.pause_btn.setText(f"Tạm dừng ({_label('pause')})")
        self.pause_btn.setIcon(icon("pause"))
        can_retry = bool(self._report and self._report.retryable_rows)
        self.retry_btn.setEnabled(not running and can_retry)
        self.export_btn.setEnabled(not running and self._report is not None)
        self.complete_changed.emit()


# Qt maps "Ctrl" to ⌘ on macOS. Mac laptops need Fn for F-keys, so each action has a ⌘ variant.
SHORTCUTS = {
    "start": ["Ctrl+R", "F5"],
    "pause": ["Ctrl+P", "F6"],
    "step": ["Ctrl+Return", "F10"],
    "stop": ["Esc", "Ctrl+."],
}


def _label(action: str) -> str:
    if action == "stop":
        return "Esc"  # the native ⎋ glyph is unfamiliar to most users
    return QKeySequence(SHORTCUTS[action][0]).toString(QKeySequence.SequenceFormat.NativeText)


def hotkey_label(pynput_hotkey: str) -> str:
    """'<ctrl>+<alt>+q' -> '⌃⌥Q' on macOS, 'Ctrl+Alt+Q' elsewhere."""
    parts = [p.strip("<>") for p in pynput_hotkey.split("+")]
    if sys.platform == "darwin":
        symbols = {"ctrl": "⌃", "alt": "⌥", "shift": "⇧", "cmd": "⌘"}
        return "".join(symbols.get(p, p.upper()) for p in parts)
    return "+".join(p.title() for p in parts)


def _button(text: str, kind: str, slot: object, symbol: IconName) -> QPushButton:
    b = QPushButton(text)
    b.setIcon(icon(symbol, "#ffffff" if kind == "primary" else "#405570"))
    if kind:
        b.setObjectName(kind)
    b.clicked.connect(slot)
    return b

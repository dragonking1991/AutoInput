import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from autoinput.core.rows import parse_rows
from autoinput.domain import AutoInputError, RowStatus, RunOptions, RunReport
from autoinput.engine import Journal, RunControl, RunEvent, Runner, start_kill_switch
from autoinput.infra.settings import get_settings
from autoinput.ui.pages.base import WizardPage, message_label, set_message
from autoinput.ui.state import AppState
from autoinput.ui.widgets.records_model import RecordsModel
from autoinput.ui.worker import RunWorker, start_worker


class RunPage(WizardPage):
    title = "3. Chạy nhập liệu"

    def __init__(self, state: AppState) -> None:
        super().__init__(state)
        self.settings = get_settings()
        self.journal = Journal(self.settings.journal_path)
        self._control: RunControl | None = None
        self._thread: QThread | None = None
        self._stop_hotkey = lambda: None
        self._report: RunReport | None = None

        # ── options ──
        self.dry_run = QCheckBox("Chạy thử (không nhập thật)")
        self.dry_run.setChecked(True)
        self.dry_run.setToolTip("Chỉ ghi log các thao tác, không điều khiển ứng dụng đích")
        self.step_mode = QCheckBox(f"Từng dòng (bấm {_label('step')} để tiếp)")
        self.stop_on_error = QCheckBox("Dừng khi gặp lỗi")
        self.rows = QLineEdit()
        self.rows.setPlaceholderText("Tất cả — hoặc vd: 1-10, 15")
        self.delay = QDoubleSpinBox(
            minimum=0, maximum=10, singleStep=0.1, value=0.3, suffix=" giây"
        )
        form = QFormLayout()
        form.addRow(self.dry_run)
        form.addRow(self.step_mode)
        form.addRow(self.stop_on_error)
        form.addRow("Chỉ các dòng:", self.rows)
        form.addRow("Nghỉ giữa các dòng:", self.delay)
        opts = QGroupBox("Tuỳ chọn")
        opts.setLayout(form)

        # ── controls ──
        self.start_btn = _button(f"▶ Bắt đầu ({_label('start')})", "primary", self.start)
        self.pause_btn = _button(f"⏸ Tạm dừng ({_label('pause')})", "", self.toggle_pause)
        self.step_btn = _button(f"⏭ Dòng tiếp ({_label('step')})", "", self.step)
        self.stop_btn = _button(f"⏹ Dừng ({_label('stop')})", "danger", self.stop)
        self.retry_btn = _button("↻ Chạy lại dòng lỗi", "", self.retry_failed)
        self.export_btn = _button("Xuất báo cáo…", "", self.export_report)
        ctrl = QVBoxLayout()
        for b in (
            self.start_btn,
            self.pause_btn,
            self.step_btn,
            self.stop_btn,
            self.retry_btn,
            self.export_btn,
        ):
            ctrl.addWidget(b)
        ctrl.addStretch()
        hint = QLabel(f"Dừng khẩn cấp bất kỳ lúc nào: {hotkey_label(self.settings.kill_switch)}")
        hint.setObjectName("hint")
        ctrl.addWidget(hint)

        self.countdown = QLabel()
        self.countdown.setObjectName("countdown")
        self.countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar()
        self.summary = message_label()
        self.model = RecordsModel(with_status=True)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setStretchLastSection(True)

        top = QHBoxLayout()
        top.addWidget(opts, 2)
        top.addLayout(ctrl, 1)
        self.root.addLayout(top)
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

    @property
    def is_running(self) -> bool:
        return self._control is not None

    def on_enter(self) -> None:
        if not self.is_running:
            self.model.set_data(self.state.columns, self.state.records)

    # ── actions ──
    def start(self) -> None:
        mapper = self.state.mapper()
        if self.is_running or not mapper or not self.state.profile:
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

        self._control = RunControl()
        try:
            runner = Runner(
                self.state.profile, mapper, options, control=self._control, journal=self.journal
            )
        except AutoInputError as e:
            self._control = None
            set_message(self.summary, f"✖ {e.message}", "error")
            return

        self.model.set_data(self.state.columns, self.state.records)
        worker = RunWorker(
            runner, self.state.records, str(self.state.source.path if self.state.source else "")
        )
        worker.event.connect(self._on_event)
        worker.failed.connect(lambda msg: set_message(self.summary, f"✖ {msg}", "error"))
        worker.done.connect(self._on_done)
        if runner.driver.needs_focus:
            self._stop_hotkey = start_kill_switch(self.settings.kill_switch, self._control.cancel)
        self._thread = start_worker(worker)
        self._set_running(True)

    def toggle_pause(self) -> None:
        if not self._control:
            return
        if self._control.is_paused:
            self._control.resume()
            self.pause_btn.setText(f"⏸ Tạm dừng ({_label('pause')})")
            set_message(self.summary, "Đang chạy…")
        else:
            self._control.pause()
            self.pause_btn.setText(f"▶ Tiếp tục ({_label('pause')})")
            set_message(self.summary, "⏸ Đã tạm dừng — sẽ dừng sau thao tác hiện tại.")

    def step(self) -> None:
        if self._control and self._control.is_paused:
            self._control.resume()

    def stop(self) -> None:
        if self._control:
            self._control.cancel()
            set_message(self.summary, "Đang dừng…")

    def retry_failed(self) -> None:
        if self._report and self._report.failed_rows:
            self.rows.setText(",".join(map(str, sorted(self._report.failed_rows))))
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
    def _on_event(self, e: RunEvent) -> None:
        match e.kind:
            case "started":
                self.progress.setRange(0, max(e.total, 1))
                self.progress.setValue(0)
                set_message(self.summary, f"Chuẩn bị nhập {e.total} dòng…")
            case "countdown":
                self.countdown.setText(f"{e.message}")
                set_message(self.summary, "Chuyển sang ứng dụng đích ngay — bắt đầu sau…")
            case "row_started" if e.row is not None:
                self.countdown.clear()
                self.model.set_status(e.row, RowStatus.RUNNING)
                if (pos := self.model.position_of(e.row)) is not None:
                    self.table.scrollTo(self.model.index(pos, 0))
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
                text = (
                    f"{'⏹ Đã dừng' if r.cancelled else '✔ Hoàn tất'}: "
                    f"{r.count(RowStatus.DONE)} xong • {r.count(RowStatus.FAILED)} thất bại • "
                    f"{r.count(RowStatus.INVALID)} dữ liệu lỗi • {r.duration_seconds:.1f}s"
                )
                set_message(self.summary, text, "error" if r.failed_rows else "ok")

    def _on_done(self) -> None:
        self._stop_hotkey()
        self._stop_hotkey = lambda: None
        self._control = None
        self._thread = None
        self.countdown.clear()
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        for w in (self.dry_run, self.step_mode, self.stop_on_error, self.rows, self.delay):
            w.setEnabled(not running)
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.step_btn.setEnabled(running)
        self.stop_btn.setEnabled(running)
        self.pause_btn.setText(f"⏸ Tạm dừng ({_label('pause')})")
        has_failed = bool(self._report and self._report.failed_rows)
        self.retry_btn.setEnabled(not running and has_failed)
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
    return QKeySequence(SHORTCUTS[action][0]).toString(QKeySequence.SequenceFormat.NativeText)


def hotkey_label(pynput_hotkey: str) -> str:
    """'<ctrl>+<alt>+q' -> '⌃⌥Q' on macOS, 'Ctrl+Alt+Q' elsewhere."""
    parts = [p.strip("<>") for p in pynput_hotkey.split("+")]
    if sys.platform == "darwin":
        symbols = {"ctrl": "⌃", "alt": "⌥", "shift": "⇧", "cmd": "⌘"}
        return "".join(symbols.get(p, p.upper()) for p in parts)
    return "+".join(p.title() for p in parts)


def _button(text: str, kind: str, slot: object) -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    b.clicked.connect(slot)
    return b

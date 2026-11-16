
My thought process
* The user wants me to analyze code, workflow, and tech stack for importing data from files (Excel, JSON, CSV, XML) into another data entry application on Windows. They want optimal solutions with:
    * Ability to debug separate flows
    * Clean and easy-to-understand UX
    * Best practices for all languages
    * Good code organization structure
* Let me design a comprehensive solution for this.I'll create a Windows desktop application that:
    1. Reads from Excel, JSON, CSV, XML files
    2. Maps the data to target application fields
    3. Automates data entry into another Windows application
    4. Has debugging capabilities for separate flows
    5. Clean UX
* Tech stack considerations: I'm weighing Python with PyAutoGUI/pywinauto, C# with WPF, or Electron.js for the automation layer. For Python I'd use pandas/openpyxl for parsing, pywinauto for UI automation, PyQt6 for the GUI, and loguru for logging, while the C# route would rely on NPOI/EPPlus for Excel handling and native Windows automation APIs.I'm settling on Python as the primary stack for its flexibility, and sketching out a folder structure with core utilities, format-specific parsers for Excel/JSON/CSV/XML, automators for Win32 and UI automation, and a mappers module to connect parsed fields to automation targets.I'm planning out the workflows and GUI components, then will move into writing full implementation code, covering the tech comparison, architecture, workflows, and best practices, structured in Vietnamese with examples.
🏗️ Data Import Automation Tool - Phân Tích & Thiết Kế
📋 Mục Lục
1. Tech Stack Analysis
2. Architecture & Workflow
3. Project Structure
4. Core Implementation
5. UX Design
6. Debug System

1. 🔧 Tech Stack Analysis

┌─────────────────────────────────────────────────────────────┐
│                    TECH STACK DECISION                       │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│   Layer     │   Option A   │   Option B   │   ✅ CHOSEN     │
├─────────────┼──────────────┼──────────────┼─────────────────┤
│ Language    │ C# WPF       │ Electron.js  │ Python 3.11+    │
│ UI          │ WPF/XAML     │ React        │ PyQt6           │
│ Automation  │ FlaUI        │ robot.js     │ pywinauto/uia   │
│ Logging     │ Serilog      │ winston      │ loguru          │
│ Config      │ appsettings  │ dotenv       │ pydantic v2     │
│ Testing     │ xUnit        │ jest         │ pytest          │
└─────────────┴──────────────┴──────────────┴─────────────────┘

WHY PYTHON:
  ✅ pandas/openpyxl/lxml - file parsing tốt nhất
  ✅ pywinauto - automation Windows app mạnh nhất
  ✅ PyQt6 - UI professional, cross-debug support
  ✅ loguru - structured logging đẹp
  ✅ pydantic - validation & config type-safe

2. 🏛️ Architecture & Workflow

┌─────────────────────────────────────────────────────────────────┐
│                     SYSTEM ARCHITECTURE                          │
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  INPUT   │    │  PARSE   │    │   MAP    │    │ AUTOMATE │  │
│  │          │───▶│          │───▶│          │───▶│          │  │
│  │ .xlsx    │    │ Parser   │    │ FieldMap │    │ Target   │  │
│  │ .json    │    │ Factory  │    │ Engine   │    │ App      │  │
│  │ .csv     │    │          │    │          │    │ (Win32)  │  │
│  │ .xml     │    │          │    │          │    │          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │               │               │               │          │
│       └───────────────┴───────────────┴───────────────┘          │
│                               │                                   │
│                    ┌──────────▼──────────┐                       │
│                    │   EVENT BUS         │                       │
│                    │   (Observable)      │                       │
│                    └──────────┬──────────┘                       │
│                               │                                   │
│              ┌────────────────┼────────────────┐                 │
│              ▼                ▼                ▼                 │
│         ┌────────┐      ┌─────────┐      ┌─────────┐           │
│         │  GUI   │      │ LOGGER  │      │ DEBUGGER│           │
│         │ PyQt6  │      │ loguru  │      │ Per-Flow│           │
│         └────────┘      └─────────┘      └─────────┘           │
└─────────────────────────────────────────────────────────────────┘

3. 📁 Project Structure

data-import-tool/
│
├── 📁 src/
│   ├── 📁 core/
│   │   ├── __init__.py
│   │   ├── config.py          # Pydantic settings
│   │   ├── logger.py          # Loguru setup
│   │   ├── exceptions.py      # Custom exceptions
│   │   └── event_bus.py       # Observable pattern
│   │
│   ├── 📁 parsers/
│   │   ├── __init__.py
│   │   ├── base_parser.py     # Abstract Protocol
│   │   ├── excel_parser.py
│   │   ├── json_parser.py
│   │   ├── csv_parser.py
│   │   └── xml_parser.py
│   │
│   ├── 📁 automators/
│   │   ├── __init__.py
│   │   ├── base_automator.py
│   │   ├── win_automator.py   # pywinauto wrapper
│   │   └── keyboard_auto.py   # fallback keyboard
│   │
│   ├── 📁 mappers/
│   │   ├── __init__.py
│   │   ├── field_mapper.py
│   │   └── transforms.py      # data transformations
│   │
│   ├── 📁 workflows/
│   │   ├── __init__.py
│   │   ├── base_workflow.py
│   │   ├── import_workflow.py
│   │   └── debug_workflow.py
│   │
│   └── 📁 gui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── 📁 panels/
│       │   ├── file_panel.py
│       │   ├── mapper_panel.py
│       │   ├── progress_panel.py
│       │   └── log_panel.py
│       └── 📁 styles/
│           └── theme.py
│
├── 📁 tests/
│   ├── 📁 unit/
│   │   ├── test_parsers.py
│   │   ├── test_mappers.py
│   │   └── test_workflows.py
│   └── 📁 integration/
│       └── test_full_flow.py
│
├── 📁 configs/
│   ├── mappings/              # JSON mapping configs
│   │   └── app_mapping.json
│   └── settings.yaml
│
├── 📁 logs/                   # Auto-generated
├── requirements.txt
├── pyproject.toml
└── main.py

4. 💻 Core Implementation
4.1 Core Config & Exceptions
python
# src/core/config.py
from pydantic_settings import BaseSettings
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Literal

class ParserConfig(BaseModel):
    encoding: str = "utf-8"
    delimiter: str = ","
    sheet_name: str | int = 0
    skip_rows: int = 0
    max_rows: int | None = None

class AutomatorConfig(BaseModel):
    target_app: str = ""
    target_exe: str = ""
    delay_between_fields: float = 0.1   # seconds
    delay_between_rows: float = 0.5
    retry_attempts: int = 3
    retry_delay: float = 1.0
    backend: Literal["win32", "uia"] = "uia"

class DebugConfig(BaseModel):
    enabled: bool = False
    step_mode: bool = False             # pause mỗi field
    screenshot_on_error: bool = True
    dry_run: bool = False               # không thực sự nhập

class AppSettings(BaseSettings):
    app_name: str = "Data Import Tool"
    version: str = "1.0.0"
    log_level: str = "INFO"
    log_dir: Path = Path("logs")
    config_dir: Path = Path("configs")

    parser: ParserConfig = ParserConfig()
    automator: AutomatorConfig = AutomatorConfig()
    debug: DebugConfig = DebugConfig()

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"

settings = AppSettings()
python
# src/core/exceptions.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ImportError(Exception):
    """Base exception cho toàn bộ import process"""
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    row_index: int | None = None

    def __str__(self):
        ctx = f" | Context: {self.context}" if self.context else ""
        row = f" | Row: {self.row_index}" if self.row_index else ""
        return f"{self.message}{row}{ctx}"

class ParseError(ImportError):
    """Lỗi khi parse file"""
    pass

class MappingError(ImportError):
    """Lỗi khi map fields"""
    pass

class AutomationError(ImportError):
    """Lỗi khi thao tác với target app"""
    pass

class ValidationError(ImportError):
    """Lỗi validate data"""
    pass
python
# src/core/event_bus.py
from collections import defaultdict
from typing import Callable, Any
from dataclasses import dataclass
from enum import Enum, auto

class EventType(Enum):
    # Parser events
    PARSE_STARTED = auto()
    PARSE_PROGRESS = auto()
    PARSE_COMPLETED = auto()
    PARSE_ERROR = auto()

    # Workflow events
    WORKFLOW_STARTED = auto()
    WORKFLOW_ROW_START = auto()
    WORKFLOW_ROW_DONE = auto()
    WORKFLOW_COMPLETED = auto()
    WORKFLOW_ERROR = auto()

    # Automation events
    FIELD_TYPING = auto()
    FIELD_DONE = auto()
    AUTOMATION_ERROR = auto()

    # Debug events
    DEBUG_STEP = auto()
    DEBUG_PAUSED = auto()

@dataclass
class Event:
    type: EventType
    data: dict[str, Any]

class EventBus:
    """Singleton Event Bus - Observable Pattern"""
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers: dict[EventType, list[Callable]] = \
                defaultdict(list)
        return cls._instance

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        self._subscribers[event_type].remove(callback)

    def emit(self, event: Event) -> None:
        for callback in self._subscribers[event.type]:
            try:
                callback(event)
            except Exception as e:
                # Không để lỗi subscriber crash main flow
                from src.core.logger import get_logger
                get_logger("event_bus").error(f"Subscriber error: {e}")

# Singleton instance
bus = EventBus()
4.2 Logger System
python
# src/core/logger.py
import sys
from pathlib import Path
from loguru import logger
from src.core.config import settings

# ─── Format Constants ──────────────────────────────────────────
CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[flow]}</cyan> | "
    ""
)

FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{extra[flow]: <20} | "
    "{name}:{line} | "
    "{message}"
)

def setup_logger():
    """Setup loguru với multiple sinks"""
    logger.remove()  # Remove default handler

    log_dir = settings.log_dir
    log_dir.mkdir(exist_ok=True)

    # ── Console sink (màu sắc) ─────────────────────────────────
    logger.add(
        sys.stdout,
        format=CONSOLE_FORMAT,
        level=settings.log_level,
        colorize=True,
        filter=lambda r: True,
    )

    # ── Main log file ──────────────────────────────────────────
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        format=FILE_FORMAT,
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )

    # ── Error log file (riêng) ─────────────────────────────────
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        format=FILE_FORMAT,
        level="ERROR",
        rotation="1 day",
        retention="30 days",
        encoding="utf-8",
    )

    # ── Per-flow debug logs ────────────────────────────────────
    for flow in ["parser", "mapper", "automator", "workflow"]:
        logger.add(
            log_dir / f"debug_{flow}.log",
            format=FILE_FORMAT,
            level="DEBUG",
            filter=lambda r, f=flow: r["extra"].get("flow") == f,
            rotation="10 MB",
            encoding="utf-8",
        )

def get_logger(flow: str):
    """Lấy logger với flow context cụ thể"""
    return logger.bind(flow=flow)

setup_logger()
4.3 Parser Factory
python
# src/parsers/base_parser.py
from abc import ABC, abstractmethod
from typing import Iterator
from dataclasses import dataclass
import pandas as pd

@dataclass
class ParsedRow:
    index: int
    data: dict[str, any]
    raw: dict[str, any]      # data gốc chưa transform
    source_file: str

class BaseParser(ABC):
    """Abstract base - mọi parser PHẢI implement"""

    def __init__(self, config=None):
        from src.core.logger import get_logger
        from src.core.config import settings
        self.log = get_logger("parser")
        self.config = config or settings.parser

    @abstractmethod
    def validate(self, file_path: str) -> bool:
        """Kiểm tra file có hợp lệ không"""
        ...

    @abstractmethod
    def parse(self, file_path: str) -> pd.DataFrame:
        """Parse file thành DataFrame"""
        ...

    def parse_iter(self, file_path: str) -> Iterator[ParsedRow]:
        """Stream parse - tốt cho file lớn"""
        df = self.parse(file_path)
        for idx, row in df.iterrows():
            yield ParsedRow(
                index=idx,
                data=row.to_dict(),
                raw=row.to_dict(),
                source_file=file_path,
            )

    def get_preview(self, file_path: str, rows: int = 5) -> pd.DataFrame:
        """Preview N rows đầu để user xác nhận mapping"""
        df = self.parse(file_path)
        return df.head(rows)
python
# src/parsers/__init__.py - Parser Factory
from pathlib import Path
from src.parsers.base_parser import BaseParser
from src.parsers.excel_parser import ExcelParser
from src.parsers.json_parser import JsonParser
from src.parsers.csv_parser import CsvParser
from src.parsers.xml_parser import XmlParser
from src.core.exceptions import ParseError

_PARSER_MAP = {
    ".xlsx": ExcelParser,
    ".xls": ExcelParser,
    ".xlsm": ExcelParser,
    ".json": JsonParser,
    ".csv": CsvParser,
    ".tsv": CsvParser,
    ".xml": XmlParser,
}

def get_parser(file_path: str, config=None) -> BaseParser:
    """Factory method - tự động chọn parser theo extension"""
    ext = Path(file_path).suffix.lower()
    parser_class = _PARSER_MAP.get(ext)

    if not parser_class:
        raise ParseError(
            message=f"Unsupported file type: {ext}",
            context={"supported": list(_PARSER_MAP.keys())}
        )

    return parser_class(config=config)
python
# src/parsers/excel_parser.py
import pandas as pd
from pathlib import Path
from src.parsers.base_parser import BaseParser
from src.core.exceptions import ParseError
from src.core.event_bus import bus, Event, EventType

class ExcelParser(BaseParser):

    def validate(self, file_path: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"File not found: {file_path}")
        if path.suffix.lower() not in {".xlsx", ".xls", ".xlsm"}:
            raise ParseError(f"Invalid Excel extension: {path.suffix}")
        return True

    def parse(self, file_path: str) -> pd.DataFrame:
        self.validate(file_path)
        self.log.info(f"Parsing Excel: {file_path}")

        bus.emit(Event(EventType.PARSE_STARTED, {"file": file_path, "type": "excel"}))

        try:
            df = pd.read_excel(
                file_path,
                sheet_name=self.config.sheet_name,
                skiprows=self.config.skip_rows,
                nrows=self.config.max_rows,
                dtype=str,                  # Giữ nguyên dạng string để tránh type coercion
                keep_default_na=False,      # Không convert empty thành NaN
            )

            # Clean column names
            df.columns = df.columns.astype(str).str.strip()
            df = df.dropna(how="all")       # Xóa rows toàn rỗng

            self.log.success(f"Parsed {len(df)} rows, {len(df.columns)} cols")
            bus.emit(Event(EventType.PARSE_COMPLETED, {
                "file": file_path,
                "rows": len(df),
                "columns": list(df.columns)
            }))
            return df

        except Exception as e:
            bus.emit(Event(EventType.PARSE_ERROR, {"file": file_path, "error": str(e)}))
            raise ParseError(
                message=f"Excel parse failed: {e}",
                context={"file": file_path}
            ) from e

    def get_sheet_names(self, file_path: str) -> list[str]:
        """Lấy danh sách sheet names"""
        with pd.ExcelFile(file_path) as xf:
            return xf.sheet_names
python
# src/parsers/csv_parser.py
import pandas as pd
import chardet
from pathlib import Path
from src.parsers.base_parser import BaseParser
from src.core.exceptions import ParseError

class CsvParser(BaseParser):

    def validate(self, file_path: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"File not found: {file_path}")
        return True

    def _detect_encoding(self, file_path: str) -> str:
        """Auto-detect encoding (UTF-8, UTF-16, cp1252...)"""
        with open(file_path, "rb") as f:
            raw = f.read(10000)
        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8")
        self.log.debug(f"Detected encoding: {encoding} ({detected['confidence']:.0%})")
        return encoding

    def _detect_delimiter(self, file_path: str, encoding: str) -> str:
        """Auto-detect delimiter"""
        import csv
        with open(file_path, encoding=encoding, errors="replace") as f:
            sample = f.read(4096)
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(sample, delimiters=",;\t|")
            return dialect.delimiter
        except csv.Error:
            return self.config.delimiter

    def parse(self, file_path: str) -> pd.DataFrame:
        self.validate(file_path)

        encoding = self._detect_encoding(file_path)
        delimiter = self._detect_delimiter(file_path, encoding)

        self.log.info(f"CSV: encoding={encoding}, delimiter='{delimiter}'")

        try:
            df = pd.read_csv(
                file_path,
                sep=delimiter,
                encoding=encoding,
                encoding_errors="replace",
                skiprows=self.config.skip_rows,
                nrows=self.config.max_rows,
                dtype=str,
                keep_default_na=False,
            )
            df.columns = df.columns.str.strip()
            return df

        except Exception as e:
            raise ParseError(
                message=f"CSV parse failed: {e}",
                context={"file": file_path, "encoding": encoding}
            ) from e
python
# src/parsers/xml_parser.py
import pandas as pd
from lxml import etree
from pathlib import Path
from src.parsers.base_parser import BaseParser
from src.core.exceptions import ParseError

class XmlParser(BaseParser):

    def validate(self, file_path: str) -> bool:
        path = Path(file_path)
        if not path.exists():
            raise ParseError(f"File not found: {file_path}")
        return True

    def parse(self, file_path: str, record_tag: str = None) -> pd.DataFrame:
        """
        record_tag: tag name của mỗi record (auto-detect nếu None)
        """
        self.validate(file_path)
        self.log.info(f"Parsing XML: {file_path}")

        try:
            tree = etree.parse(file_path)
            root = tree.getroot()

            # Auto-detect record tag (child elements của root)
            if not record_tag:
                children = list(root)
                if not children:
                    raise ParseError("XML has no child elements")
                record_tag = children[0].tag
                self.log.debug(f"Auto-detected record tag: <{record_tag}>")

            records = []
            for elem in root.iter(record_tag):
                row = {}
                # Lấy attributes
                row.update(elem.attrib)
                # Lấy child elements text
                for child in elem:
                    tag = child.tag.split("}")[-1]  # Remove namespace
                    row[tag] = (child.text or "").strip()
                records.append(row)

            df = pd.DataFrame(records).fillna("")
            self.log.success(f"Parsed {len(df)} XML records")
            return df

        except etree.XMLSyntaxError as e:
            raise ParseError(
                message=f"Invalid XML syntax: {e}",
                context={"file": file_path}
            ) from e
4.4 Field Mapper
python
# src/mappers/field_mapper.py
from dataclasses import dataclass, field
from typing import Callable, Any
import json
from pathlib import Path
from src.core.logger import get_logger
from src.core.exceptions import MappingError

@dataclass
class FieldRule:
    """Quy tắc mapping một field"""
    source_column: str           # Tên cột trong file
    target_field: str            # Tên field trong app đích
    required: bool = False
    default_value: str = ""
    transforms: list[str] = field(default_factory=list)  # ["strip", "upper", "date_vn"]
    validator: str | None = None

@dataclass
class MappingConfig:
    """Full mapping configuration"""
    name: str
    source_fields: list[str]
    rules: list[FieldRule]
    version: str = "1.0"

    def to_json(self, path: str):
        data = {
            "name": self.name,
            "version": self.version,
            "rules": [
                {
                    "source_column": r.source_column,
                    "target_field": r.target_field,
                    "required": r.required,
                    "default_value": r.default_value,
                    "transforms": r.transforms,
                }
                for r in self.rules
            ]
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def from_json(cls, path: str) -> "MappingConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        rules = [FieldRule(**r) for r in data["rules"]]
        return cls(
            name=data["name"],
            source_fields=[r.source_column for r in rules],
            rules=rules,
            version=data.get("version", "1.0"),
        )

class FieldMapper:
    """Map và transform data từ source sang target format"""

    TRANSFORM_MAP: dict[str, Callable] = {
        "strip": str.strip,
        "upper": str.upper,
        "lower": str.lower,
        "title": str.title,
        "remove_spaces": lambda x: x.replace(" ", ""),
        "digits_only": lambda x: "".join(c for c in x if c.isdigit()),
        "date_vn_to_iso": lambda x: _convert_date_vn(x),   # DD/MM/YYYY → YYYY-MM-DD
        "comma_to_dot": lambda x: x.replace(",", "."),
        "phone_normalize": lambda x: _normalize_phone(x),
    }

    def __init__(self, config: MappingConfig):
        self.config = config
        self.log = get_logger("mapper")

    def map_row(self, raw_data: dict[str, Any]) -> dict[str, str]:
        """Map một row data theo config"""
        result = {}

        for rule in self.config.rules:
            try:
                value = raw_data.get(rule.source_column, rule.default_value)
                value = str(value).strip() if value else rule.default_value

                # Apply transforms theo thứ tự
                for transform_name in rule.transforms:
                    transform_fn = self.TRANSFORM_MAP.get(transform_name)
                    if transform_fn:
                        value = transform_fn(value)
                    else:
                        self.log.warning(f"Unknown transform: {transform_name}")

                # Check required
                if rule.required and not value:
                    raise MappingError(
                        message=f"Required field missing: {rule.source_column}",
                        context={"rule": rule.target_field, "data": raw_data}
                    )

                result[rule.target_field] = value
                self.log.debug(
                    f"Mapped: '{rule.source_column}' → '{rule.target_field}' = '{value}'"
                )

            except MappingError:
                raise
            except Exception as e:
                raise MappingError(
                    message=f"Mapping failed for field '{rule.source_column}': {e}",
                    context={"rule": rule.__dict__}
                ) from e

        return result

# ─── Transform helpers ──────────────────────────────────────────
def _convert_date_vn(date_str: str) -> str:
    from datetime import datetime
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str

def _normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    return digits
4.5 Windows Automator
python
# src/automators/win_automator.py
import time
import pyperclip
from typing import Callable
from dataclasses import dataclass
import pywinauto
from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys

from src.core.logger import get_logger
from src.core.config import settings
from src.core.exceptions import AutomationError
from src.core.event_bus import bus, Event, EventType

@dataclass
class FieldAction:
    """Định nghĩa cách tương tác với một field"""
    field_name: str             # Tên logical
    locator: str                # auto_id, title, class_name
    locator_type: str = "auto_id"  # auto_id | title | class_name | xpath
    action: str = "type"        # type | click | select | check
    tab_after: bool = True      # Nhấn Tab sau khi nhập
    clear_first: bool = True    # Xóa nội dung cũ
    use_clipboard: bool = False  # Dùng clipboard thay vì gõ phím

class WindowsAutomator:
    """Tự động hóa thao tác trên Windows app"""

    def __init__(self, config=None):
        self.log = get_logger("automator")
        self.cfg = config or settings.automator
        self.app: Application | None = None
        self.window = None
        self._field_actions: dict[str, FieldAction] = {}
        self._screenshots_dir = settings.log_dir / "screenshots"
        self._screenshots_dir.mkdir(exist_ok=True)

    def connect_or_launch(self) -> bool:
        """Kết nối với app đang chạy hoặc khởi động mới"""
        try:
            # Thử kết nối app đang chạy
            self.app = Application(backend=self.cfg.backend).connect(
                title_re=f".*{self.cfg.target_app}.*",
                timeout=5
            )
            self.log.info(f"Connected to running app: {self.cfg.target_app}")

        except pywinauto.findwindows.ElementNotFoundError:
            # Khởi động mới nếu chưa chạy
            if not self.cfg.target_exe:
                raise AutomationError("App not running and no target_exe configured")

            self.log.info(f"Launching: {self.cfg.target_exe}")
            self.app = Application(backend=self.cfg.backend).start(
                self.cfg.target_exe,
                wait_for_idle=True
            )
            time.sleep(2)

        self.window = self.app.top_window()
        self.log.success(f"Window ready: '{self.window.window_text()}'")
        return True

    def register_field(self, action: FieldAction):
        """Đăng ký cách tương tác với field"""
        self._field_actions[action.field_name] = action

    def register_fields(self, actions: list[FieldAction]):
        for action in actions:
            self.register_field(action)

    def _find_control(self, action: FieldAction):
        """Tìm control theo locator type"""
        kwargs = {action.locator_type: action.locator}
        try:
            ctrl = self.window.child_window(**kwargs)
            ctrl.wait("visible", timeout=5)
            return ctrl
        except Exception as e:
            raise AutomationError(
                message=f"Control not found: {action.field_name}",
                context={"locator": action.locator, "type": action.locator_type},
            ) from e

    def type_field(self, field_name: str, value: str) -> bool:
        """Nhập giá trị vào một field"""
        if field_name not in self._field_actions:
            raise AutomationError(f"Field not registered: {field_name}")

        action = self._field_actions[field_name]

        # Dry run mode - không thực sự nhập
        if settings.debug.dry_run:
            self.log.debug(f"[DRY RUN] Would type '{value}' into '{field_name}'")
            return True

        bus.emit(Event(EventType.FIELD_TYPING, {
            "field": field_name,
            "value": value[:20] + "..." if len(value) > 20 else value
        }))

        for attempt in range(self.cfg.retry_attempts):
            try:
                ctrl = self._find_control(action)
                ctrl.set_focus()

                if action.clear_first:
                    ctrl.select()  # Select all
                    send_keys("^a{DELETE}")

                if action.use_clipboard or len(value) > 50:
                    # Dùng clipboard cho text dài (nhanh hơn)
                    pyperclip.copy(value)
                    send_keys("^v")
                else:
                    ctrl.type_keys(value, with_spaces=True)

                if action.tab_after:
                    time.sleep(0.05)
                    send_keys("{TAB}")

                time.sleep(self.cfg.delay_between_fields)
                bus.emit(Event(EventType.FIELD_DONE, {"field": field_name}))
                return True

            except AutomationError:
                raise
            except Exception as e:
                self.log.warning(
                    f"Attempt {attempt+1}/{self.cfg.retry_attempts} failed "
                    f"for '{field_name}': {e}"
                )
                if attempt < self.cfg.retry_attempts - 1:
                    time.sleep(self.cfg.retry_delay)

        raise AutomationError(
            message=f"Failed to type into '{field_name}' after {self.cfg.retry_attempts} attempts"
        )

    def type_row(
        self,
        mapped_data: dict[str, str],
        on_field_done: Callable | None = None
    ) -> bool:
        """Nhập toàn bộ một row theo thứ tự field đã đăng ký"""
        self.log.debug(f"Typing row with {len(mapped_data)} fields")

        for field_name, value in mapped_data.items():
            self.type_field(field_name, value)
            if on_field_done:
                on_field_done(field_name, value)

        time.sleep(self.cfg.delay_between_rows)
        return True

    def take_screenshot(self, prefix: str = "screenshot") -> str:
        """Chụp screenshot để debug"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H%M%S_%f")
        path = self._screenshots_dir / f"{prefix}_{timestamp}.png"
        try:
            self.window.capture_as_image().save(str(path))
            self.log.debug(f"Screenshot saved: {path}")
            return str(path)
        except Exception:
            return ""
4.6 Main Workflow
python
# src/workflows/import_workflow.py
from dataclasses import dataclass, field
from typing import Iterator, Callable
from enum import Enum, auto
import time

from src.core.logger import get_logger
from src.core.event_bus import bus, Event, EventType
from src.core.exceptions import ImportError, AutomationError
from src.parsers import get_parser
from src.parsers.base_parser import ParsedRow
from src.mappers.field_mapper import FieldMapper, MappingConfig
from src.automators.win_automator import WindowsAutomator
from src.core.config import settings

class WorkflowStatus(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

@dataclass
class WorkflowResult:
    total_rows: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    errors: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if not self.total_rows:
            return 0.0
        return self.success_count / self.total_rows * 100

class ImportWorkflow:
    """
    Main workflow điều phối toàn bộ quá trình import.
    Supports: pause, resume, step-mode, cancel
    """

    def __init__(
        self,
        parser_config=None,
        mapping_config: MappingConfig = None,
        automator: WindowsAutomator = None,
    ):
        self.log = get_logger("workflow")
        self.parser_config = parser_config
        self.mapping_config = mapping_config
        self.automator = automator or WindowsAutomator()
        self.mapper = FieldMapper(mapping_config) if mapping_config else None

        self._status = WorkflowStatus.IDLE
        self._cancel_flag = False
        self._pause_flag = False
        self._step_mode = settings.debug.step_mode
        self._step_continue_flag = False

        # Callbacks
        self.on_row_done: Callable | None = None
        self.on_error: Callable | None = None

    @property
    def status(self) -> WorkflowStatus:
        return self._status

    def cancel(self):
        self._cancel_flag = True
        self.log.warning("Workflow cancel requested")

    def pause(self):
        self._pause_flag = True
        self._status = WorkflowStatus.PAUSED
        self.log.info("Workflow paused")

    def resume(self):
        self._pause_flag = False
        self._step_continue_flag = True
        self._status = WorkflowStatus.RUNNING
        self.log.info("Workflow resumed")

    def step_continue(self):
        """Trong step mode: tiếp tục một bước"""
        self._step_continue_flag = True

    def _wait_if_paused(self):
        """Block nếu đang pause (trong step mode)"""
        while self._pause_flag:
            if self._cancel_flag:
                break
            time.sleep(0.1)

    def run(self, file_path: str) -> WorkflowResult:
        """
        Main execution method.
        Returns WorkflowResult với đầy đủ statistics.
        """
        result = WorkflowResult()
        start_time = time.time()
        self._status = WorkflowStatus.RUNNING
        self._cancel_flag = False

        self.log.info(f"═══ Workflow started: {file_path} ═══")
        bus.emit(Event(EventType.WORKFLOW_STARTED, {"file": file_path}))

        try:
            # ── Step 1: Parse file ─────────────────────────────────
            parser = get_parser(file_path, config=self.parser_config)
            rows: list[ParsedRow] = list(parser.parse_iter(file_path))
            result.total_rows = len(rows)
            self.log.info(f"Total rows to process: {result.total_rows}")

            # ── Step 2: Connect to target app ──────────────────────
            self.automator.connect_or_launch()

            # ── Step 3: Process rows ───────────────────────────────
            for parsed_row in rows:
                # Check cancel
                if self._cancel_flag:
                    self.log.warning(f"Cancelled at row {parsed_row.index}")
                    self._status = WorkflowStatus.CANCELLED
                    break

                # Check pause / step mode
                self._wait_if_paused()

                bus.emit(Event(EventType.WORKFLOW_ROW_START, {
                    "index": parsed_row.index,
                    "total": result.total_rows,
                }))

                success = self._process_row(parsed_row, result)

                if success:
                    result.success_count += 1
                    bus.emit(Event(EventType.WORKFLOW_ROW_DONE, {
                        "index": parsed_row.index,
                        "success": True,
                    }))
                    if self.on_row_done:
                        self.on_row_done(parsed_row.index, result)

                # Step mode: pause sau mỗi row
                if self._step_mode and not self._cancel_flag:
                    self.pause()
                    bus.emit(Event(EventType.DEBUG_PAUSED, {
                        "row": parsed_row.index,
                        "data": parsed_row.data
                    }))

        except Exception as e:
            self._status = WorkflowStatus.FAILED
            self.log.critical(f"Workflow failed: {e}")
            raise

        finally:
            result.duration_seconds = time.time() - start_time
            if self._status == WorkflowStatus.RUNNING:
                self._status = WorkflowStatus.COMPLETED

            self.log.info(
                f"═══ Workflow done ═══ "
                f"✅{result.success_count} "
                f"❌{result.failed_count} "
                f"⏱{result.duration_seconds:.1f}s"
            )
            bus.emit(Event(EventType.WORKFLOW_COMPLETED, {
                "result": result.__dict__
            }))

        return result

    def _process_row(self, parsed_row: ParsedRow, result: WorkflowResult) -> bool:
        """Xử lý một row: map → validate → type"""
        try:
            # Map fields
            mapped_data = self.mapper.map_row(parsed_row.data)

            # Type into app
            self.automator.type_row(mapped_data)

            self.log.info(f"✅ Row {parsed_row.index} done")
            return True

        except ImportError as e:
            e.row_index = parsed_row.index
            result.failed_count += 1
            result.errors.append({
                "row": parsed_row.index,
                "error": str(e),
                "data": parsed_row.data,
            })

            if settings.debug.screenshot_on_error:
                self.automator.take_screenshot(f"error_row{parsed_row.index}")

            self.log.error(f"❌ Row {parsed_row.index} failed: {e}")

            if self.on_error:
                self.on_error(parsed_row.index, e)

            bus.emit(Event(EventType.WORKFLOW_ERROR, {
                "row": parsed_row.index,
                "error": str(e)
            }))
            return False
4.7 GUI - Main Window
python
# src/gui/main_window.py
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QSplitter, QTabWidget, QStatusBar,
    QMenuBar, QMenu, QToolBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon

from src.gui.panels.file_panel import FilePanel
from src.gui.panels.mapper_panel import MapperPanel
from src.gui.panels.progress_panel import ProgressPanel
from src.gui.panels.log_panel import LogPanel
from src.gui.styles.theme import apply_theme
from src.core.event_bus import bus, EventType, Event
from src.core.config import settings

class WorkflowThread(QThread):
    """Chạy workflow trong thread riêng để không block UI"""
    row_done = pyqtSignal(int, object)
    completed = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, workflow, file_path: str):
        super().__init__()
        self.workflow = workflow
        self.file_path = file_path

    def run(self):
        try:
            result = self.workflow.run(self.file_path)
            self.completed.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"⚡ {settings.app_name} v{settings.version}")
        self.setMinimumSize(1200, 750)
        self._workflow_thread: WorkflowThread | None = None
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._connect_events()
        apply_theme(self)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ── Top: File + Mapper ─────────────────────────────────────
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.file_panel = FilePanel()
        self.mapper_panel = MapperPanel()

        top_splitter.addWidget(self.file_panel)
        top_splitter.addWidget(self.mapper_panel)
        top_splitter.setSizes([400, 800])

        # ── Bottom: Progress + Logs (tabs) ─────────────────────────
        self.bottom_tabs = QTabWidget()
        self.progress_panel = ProgressPanel()
        self.log_panel = LogPanel()

        self.bottom_tabs.addTab(self.progress_panel, "📊 Tiến Trình")
        self.bottom_tabs.addTab(self.log_panel, "📋 Logs")

        # ── Main splitter ──────────────────────────────────────────
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.bottom_tabs)
        main_splitter.setSizes([350, 400])

        main_layout.addWidget(main_splitter)

        # ── Status bar ─────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sẵn sàng")

    def _setup_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        open_action = QAction("📂 Mở File...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.file_panel.browse_file)

        save_mapping = QAction("💾 Lưu Mapping...", self)
        save_mapping.triggered.connect(self.mapper_panel.save_mapping)

        file_menu.addAction(open_action)
        file_menu.addAction(save_mapping)
        file_menu.addSeparator()
        file_menu.addAction("Thoát", self.close)

        # Debug menu
        debug_menu = menubar.addMenu("🔧 Debug")
        self.dry_run_action = QAction("Dry Run (không nhập thật)", self, checkable=True)
        self.step_mode_action = QAction("Step Mode (từng dòng)", self, checkable=True)
        debug_menu.addAction(self.dry_run_action)
        debug_menu.addAction(self.step_mode_action)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.run_btn = QAction("▶ Chạy Import", self)
        self.run_btn.setShortcut("F5")
        self.run_btn.triggered.connect(self._start_workflow)

        self.pause_btn = QAction("⏸ Tạm Dừng", self)
        self.pause_btn.triggered.connect(self._pause_workflow)
        self.pause_btn.setEnabled(False)

        self.stop_btn = QAction("⏹ Dừng", self)
        self.stop_btn.triggered.connect(self._stop_workflow)
        self.stop_btn.setEnabled(False)

        self.step_btn = QAction("⏭ Tiếp (Step)", self)
        self.step_btn.setShortcut("F10")
        self.step_btn.triggered.connect(self._step_workflow)
        self.step_btn.setEnabled(False)

        toolbar.addAction(self.run_btn)
        toolbar.addSeparator()
        toolbar.addAction(self.pause_btn)
        toolbar.addAction(self.step_btn)
        toolbar.addAction(self.stop_btn)

    def _connect_events(self):
        """Subscribe EventBus events → update UI"""
        bus.subscribe(EventType.WORKFLOW_ROW_DONE, self._on_row_done)
        bus.subscribe(EventType.WORKFLOW_COMPLETED, self._on_workflow_done)
        bus.subscribe(EventType.DEBUG_PAUSED, self._on_debug_paused)
        bus.subscribe(EventType.FIELD_TYPING, self._on_field_typing)

    def _start_workflow(self):
        """Khởi chạy workflow trong background thread"""
        file_path = self.file_panel.current_file
        if not file_path:
            self.status_bar.showMessage("⚠️ Chưa chọn file!")
            return

        from src.workflows.import_workflow import ImportWorkflow
        from src.automators.win_automator import WindowsAutomator

        mapping_config = self.mapper_panel.get_mapping_config()
        if not mapping_config:
            self.status_bar.showMessage("⚠️ Chưa cấu hình field mapping!")
            return

        # Apply debug settings
        settings.debug.dry_run = self.dry_run_action.isChecked()
        settings.debug.step_mode = self.step_mode_action.isChecked()

        workflow = ImportWorkflow(mapping_config=mapping_config)
        self._workflow_thread = WorkflowThread(workflow, file_path)
        self._workflow_thread.completed.connect(self._on_workflow_completed_qt)
        self._workflow_thread.error.connect(self._on_workflow_error_qt)
        self._workflow_thread.start()

        # Update UI state
        self.run_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.progress_panel.reset()
        self.status_bar.showMessage("🚀 Đang chạy...")
        self.bottom_tabs.setCurrentIndex(0)

    def _pause_workflow(self):
        if self._workflow_thread and self._workflow_thread.workflow:
            self._workflow_thread.workflow.pause()
            self.step_btn.setEnabled(True)
            self.status_bar.showMessage("⏸ Đã tạm dừng")

    def _step_workflow(self):
        if self._workflow_thread and self._workflow_thread.workflow:
            self._workflow_thread.workflow.step_continue()

    def _stop_workflow(self):
        if self._workflow_thread and self._workflow_thread.workflow:
            self._workflow_thread.workflow.cancel()
            self.status_bar.showMessage("⏹ Đang dừng...")

    # ── EventBus callbacks (cross-thread safe via signals) ─────────
    def _on_row_done(self, event: Event):
        self.progress_panel.update_progress(
            event.data["index"],
            event.data["total"]
        )

    def _on_workflow_done(self, event: Event):
        pass  # Handled by thread signal

    def _on_debug_paused(self, event: Event):
        self.status_bar.showMessage(
            f"⏸ Paused at row {event.data['row']} - Nhấn F10 để tiếp tục"
        )
        self.step_btn.setEnabled(True)

    def _on_field_typing(self, event: Event):
        self.status_bar.showMessage(
            f"⌨️ Đang nhập: [{event.data['field']}] = {event.data['value']}"
        )

    def _on_workflow_completed_qt(self, result):
        self.run_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.step_btn.setEnabled(False)
        self.progress_panel.show_result(result)
        self.status_bar.showMessage(
            f"✅ Hoàn thành! {result.success_count}/{result.total_rows} dòng "
            f"thành công ({result.success_rate:.0f}%) "
            f"- {result.duration_seconds:.1f}s"
        )

    def _on_workflow_error_qt(self, error_msg: str):
        self.run_btn.setEnabled(True)
        self.status_bar.showMessage(f"❌ Lỗi: {error_msg}")
4.8 Theme & Styles
python
# src/gui/styles/theme.py
DARK_THEME = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QToolBar {
    background: #181825;
    border-bottom: 1px solid #313244;
    padding: 4px;
    spacing: 6px;
}

QToolButton {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #cdd6f4;
}
QToolButton:hover   { background: #45475a; }
QToolButton:pressed { background: #585b70; }
QToolButton:disabled { color: #585b70; }

QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 6px;
}
QTabBar::tab {
    background: #181825;
    border: 1px solid #313244;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #313244; color: #89b4fa; }
QTabBar::tab:hover    { background: #2a2a3e; }

QTableWidget {
    background: #181825;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 6px;
}
QTableWidget::item:selected { background: #45475a; }
QHeaderView::section {
    background: #313244;
    padding: 6px;
    border: none;
    font-weight: bold;
}

QPushButton {
    background: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover   { background: #b4befe; }
QPushButton:pressed { background: #74c7ec; }

QProgressBar {
    border: 1px solid #313244;
    border-radius: 4px;
    height: 12px;
    text-align: center;
}
QProgressBar::chunk { background: #89b4fa; border-radius: 4px; }

QTextEdit {
    background: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    font-family: "Consolas", monospace;
    font-size: 12px;
}

QStatusBar {
    background: #181825;
    border-top: 1px solid #313244;
    color: #a6adc8;
    padding: 4px 8px;
}

QSplitter::handle {
    background: #313244;
    width: 2px;
    height: 2px;
}
"""

def apply_theme(app_or_widget):
    app_or_widget.setStyleSheet(DARK_THEME)

5. 📊 Debug Flow Diagram

┌─────────────────────────────────────────────────────────────────────┐
│                    DEBUG WORKFLOW MODES                              │
│                                                                      │
│  MODE 1: NORMAL RUN                                                  │
│  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐                  │
│  │ R1 │─▶│ R2 │─▶│ R3 │─▶│ R4 │─▶│ R5 │─▶│ Rn │                  │
│  └────┘  └────┘  └────┘  └────┘  └────┘  └────┘                  │
│                                                                      │
│  MODE 2: STEP MODE (F10 to advance)                                  │
│  ┌────┐  ⏸PAUSE  ┌────┐  ⏸PAUSE  ┌────┐  ⏸PAUSE                 │
│  │ R1 │──────────▶│ R2 │──────────▶│ R3 │──────────▶...           │
│  └────┘           └────┘           └────┘                          │
│         [F10]              [F10]              [F10]                  │
│                                                                      │
│  MODE 3: DRY RUN (no actual input, logs only)                       │
│  ┌────┐  ┌────┐  ┌────┐                                            │
│  │ R1 │─▶│ R2 │─▶│ R3 │─▶  ALL LOGGED, NOTHING TYPED              │
│  └────┘  └────┘  └────┘                                            │
│                                                                      │
│  SEPARATE DEBUG LOGS:                                                │
│  logs/debug_parser.log     ← chỉ parser events                      │
│  logs/debug_mapper.log     ← chỉ mapping events                     │
│  logs/debug_automator.log  ← chỉ UI automation events               │
│  logs/debug_workflow.log   ← chỉ workflow orchestration             │
│  logs/errors_YYYY-MM-DD.log← chỉ errors                            │
│  logs/screenshots/         ← auto-screenshot on error               │
└─────────────────────────────────────────────────────────────────────┘

6. ⚙️ Configuration Files
json
// configs/mappings/app_mapping.json
{
  "name": "Mapping Config v1",
  "version": "1.0",
  "rules": [
    {
      "source_column": "Họ và Tên",
      "target_field": "full_name",
      "required": true,
      "default_value": "",
      "transforms": ["strip", "title"]
    },
    {
      "source_column": "Ngày Sinh",
      "target_field": "birth_date",
      "required": true,
      "default_value": "",
      "transforms": ["strip", "date_vn_to_iso"]
    },
    {
      "source_column": "Số CCCD",
      "target_field": "id_number",
      "required": true,
      "default_value": "",
      "transforms": ["strip", "digits_only"]
    },
    {
      "source_column": "Điện Thoại",
      "target_field": "phone",
      "required": false,
      "default_value": "",
      "transforms": ["strip", "phone_normalize"]
    }
  ]
}
toml
# pyproject.toml
[tool.poetry]
name = "data-import-tool"
version = "1.0.0"
description = "Windows Data Import Automation Tool"

[tool.poetry.dependencies]
python = "^3.11"
PyQt6 = "^6.6.0"
pandas = "^2.1.0"
openpyxl = "^3.1.2"
lxml = "^4.9.3"
pywinauto = "^0.6.8"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
loguru = "^0.7.2"
chardet = "^5.2.0"
pyperclip = "^1.8.2"

[tool.poetry.dev-dependencies]
pytest = "^7.4.0"
pytest-qt = "^4.2.0"
ruff = "^0.1.0"
mypy = "^1.7.0"

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true

7. 🧪 Testing
python
# tests/unit/test_parsers.py
import pytest
import pandas as pd
from pathlib import Path
from src.parsers import get_parser
from src.core.exceptions import ParseError

@pytest.fixture
def sample_excel(tmp_path):
    df = pd.DataFrame({
        "Họ và Tên": ["Nguyễn Văn A", "Trần Thị B"],
        "Ngày Sinh": ["01/01/1990", "15/06/1985"],
        "Số CCCD": ["012345678901", "098765432109"],
    })
    path = tmp_path / "test.xlsx"
    df.to_excel(path, index=False)
    return str(path)

class TestExcelParser:
    def test_parse_returns_dataframe(self, sample_excel):
        parser = get_parser(sample_excel)
        df = parser.parse(sample_excel)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_columns_preserved(self, sample_excel):
        parser = get_parser(sample_excel)
        df = parser.parse(sample_excel)
        assert "Họ và Tên" in df.columns
        assert "Ngày Sinh" in df.columns

    def test_unsupported_extension_raises(self, tmp_path):
        fake_file = tmp_path / "test.docx"
        fake_file.touch()
        with pytest.raises(ParseError, match="Unsupported file type"):
            get_parser(str(fake_file))

    def test_file_not_found_raises(self):
        with pytest.raises(ParseError, match="File not found"):
            parser = get_parser("nonexistent.xlsx")
            parser.parse("nonexistent.xlsx")

# tests/unit/test_mappers.py
from src.mappers.field_mapper import FieldMapper, MappingConfig, FieldRule
from src.core.exceptions import MappingError

class TestFieldMapper:
    def setup_method(self):
        self.config = MappingConfig(
            name="Test",
            source_fields=["name", "date"],
            rules=[
                FieldRule(
                    source_column="name",
                    target_field="full_name",
                    required=True,
                    transforms=["strip", "title"]
                ),
                FieldRule(
                    source_column="date",
                    target_field="birth_date",
                    transforms=["strip", "date_vn_to_iso"]
                ),
            ]
        )
        self.mapper = FieldMapper(self.config)

    def test_basic_mapping(self):
        result = self.mapper.map_row({"name": "  nguyễn văn a  ", "date": "01/01/1990"})
        assert result["full_name"] == "Nguyễn Văn A"

    def test_date_transform(self):
        result = self.mapper.map_row({"name": "Test", "date": "15/06/1985"})
        assert result["birth_date"] == "1985-06-15"

    def test_required_field_missing_raises(self):
        with pytest.raises(MappingError, match="Required field missing"):
            self.mapper.map_row({"name": "", "date": "01/01/1990"})

8. 🚀 Entry Point
python
# main.py
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.gui.main_window import MainWindow
from src.core.logger import get_logger

log = get_logger("main")

def main():
    log.info("═══════════════════════════════")
    log.info("   Data Import Tool Starting   ")
    log.info("═══════════════════════════════")

    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    app.setApplicationName("Data Import Tool")
    app.setOrganizationName("YourCompany")

    window = MainWindow()
    window.show()

    log.info("UI loaded, entering event loop")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

📌 Summary & Best Practices

┌─────────────────────────────────────────────────────────────────┐
│                    BEST PRACTICES APPLIED                        │
├────────────────────────┬────────────────────────────────────────┤
│ Pattern                │ Áp dụng                                │
├────────────────────────┼────────────────────────────────────────┤
│ Factory Pattern        │ Parser Factory theo file extension      │
│ Observer/Event Bus     │ Decoupled UI ↔ Business Logic          │
│ Strategy Pattern       │ Transform functions pluggable          │
│ Abstract Base Class    │ BaseParser, BaseAutomator              │
│ Repository Pattern     │ MappingConfig serializable to JSON     │
│ Thread Safety          │ Worker thread + Qt signals             │
│ Structured Logging     │ Per-flow log files với loguru          │
│ Type Safety            │ Pydantic v2 + type hints strict        │
│ Fail Fast              │ Custom exceptions với context          │
│ Debug Modes            │ dry_run, step_mode, screenshot         │
│ Auto-detect            │ encoding, delimiter, XML record tag    │
│ Retry Logic            │ Configurable retry cho automation      │
└────────────────────────┴────────────────────────────────────────┘

QUICK START:
  pip install poetry
  poetry install
  poetry run python main.py

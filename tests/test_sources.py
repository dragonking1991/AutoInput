import json
from pathlib import Path

import pytest

from autoinput.domain import SourceError, SourceOptions
from autoinput.sources import open_source


def test_csv_autodetects_delimiter_and_keeps_unicode(samples: Path) -> None:
    src = open_source(samples / "customers.csv")
    assert src.columns()[0] == "Họ và Tên"
    records = list(src.records())
    assert len(records) == 3
    assert records[0].index == 1
    assert records[1].data["Số CCCD"] == "98765432109"


def test_json_finds_nested_list(samples: Path) -> None:
    records = open_source(samples / "customers.json").preview()
    assert [r.data["Họ và Tên"] for r in records] == ["Phạm Thị Dung", "Hoàng Văn Em"]


def test_json_flattens_nested_objects(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text(json.dumps([{"a": {"b": 1}, "tags": [1, 2]}]))
    (rec,) = open_source(path).records()
    assert rec.data == {"a.b": "1", "tags": "[1, 2]"}


def test_json_record_path(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"data": {"items": [{"k": "v"}]}}))
    (rec,) = open_source(path, SourceOptions(record_path="data.items")).records()
    assert rec.data == {"k": "v"}


def test_xml_records_with_attributes(samples: Path) -> None:
    records = open_source(samples / "customers.xml").preview()
    assert records[0].data == {
        "@id": "1",
        "name": "Võ Thị Giang",
        "birth": "05/05/1995",
        "phone": "0933111222",
    }


def test_xml_rejects_entity_expansion(tmp_path: Path) -> None:
    path = tmp_path / "bomb.xml"
    path.write_text('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><r><i>&a;</i></r>')
    with pytest.raises(SourceError):
        list(open_source(path).records())


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "x.docx"
    path.touch()
    with pytest.raises(SourceError, match="Unsupported"):
        open_source(path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="not found"):
        open_source(tmp_path / "nope.csv")

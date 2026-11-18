from pathlib import Path

import pytest

from autoinput.domain import FieldSpec, Mapping, Profile, Step
from autoinput.infra.storage import load_mapping, load_profile

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from autoinput.infra.settings import get_settings

    monkeypatch.setenv("AUTOINPUT_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()


@pytest.fixture
def samples() -> Path:
    return ROOT / "samples"


@pytest.fixture
def merged_workbook(tmp_path: Path) -> Path:
    from zipfile import ZipFile

    path = tmp_path / "merged.xlsx"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        )
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Merged" sheetId="1" r:id="rId1"/>'
            '<sheet name="Other" sheetId="2" r:id="rId2"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet2.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<dimension ref="B2:D12"/><sheetData>'
            '<row r="2"><c r="B2" t="inlineStr"><is><t>Report</t></is></c></row>'
            '<row r="4"><c r="B4" t="inlineStr"><is><t>Name</t></is></c>'
            '<c r="C4" t="inlineStr"><is><t>Income</t></is></c></row>'
            '<row r="5"><c r="C5" t="inlineStr"><is><t>Base</t></is></c>'
            '<c r="D5" t="inlineStr"><is><t>Bonus</t></is></c></row>'
            '<row r="6"><c r="B6" t="inlineStr"><is><t>Example</t></is></c>'
            '<c r="C6"><v>10</v></c><c r="D6"><v>20</v></c></row>'
            '<row r="8"><c r="B8" t="inlineStr"><is><t>Footer</t></is></c></row>'
            '<row r="12"><c r="D12"><v>30</v></c></row>'
            '</sheetData><mergeCells count="4"><mergeCell ref="B2:D2"/>'
            '<mergeCell ref="B4:B5"/><mergeCell ref="C4:D4"/>'
            '<mergeCell ref="B8:B12"/></mergeCells></worksheet>',
        )
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<dimension ref="A1:A2"/><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Code</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>Example</t></is></c></row>'
            '</sheetData></worksheet>',
        )
    return path


@pytest.fixture
def crm_profile() -> Profile:
    return load_profile(ROOT / "profiles" / "crm_customer.yaml")


@pytest.fixture
def crm_mapping() -> Mapping:
    return load_mapping(ROOT / "mappings" / "crm_customer.yaml")


@pytest.fixture
def simple_profile() -> Profile:
    return Profile(
        id="p",
        name="P",
        fields={
            "name": FieldSpec(locator={"auto_id": "n"}),
            "code": FieldSpec(locator={"auto_id": "c"}),
        },
        controls={"save": {"auto_id": "s"}},
        record_steps=[Step(action="fill_all"), Step(action="click", target="save")],
    )

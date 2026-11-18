import pytest

from autoinput.core.rows import parse_rows
from autoinput.domain import ConfigError, FieldMap, Mapping, Profile, Record
from autoinput.mapping import Mapper, suggest_mapping
from autoinput.transforms import apply_transforms


@pytest.mark.parametrize(
    ("value", "specs", "expected"),
    [
        ("  nguyễn  văn an ", ["collapse_spaces", "title"], "Nguyễn Văn An"),
        ("15-06-1985", ["date:%Y-%m-%d"], "1985-06-15"),
        ("+84 912 345 678", ["phone_vn"], "0912345678"),
        ("123", ["pad_left:6"], "000123"),
        ("M", ["map:M=Nam,F=Nữ"], "Nam"),
        ("Đặng Hùng", ["no_accents"], "Dang Hung"),
    ],
)
def test_transforms(value: str, specs: list[str], expected: str) -> None:
    assert apply_transforms(value, specs) == expected


def test_mapper_collects_all_errors(crm_profile: Profile) -> None:
    mapping = Mapping(
        name="Validation test",
        profile=crm_profile.id,
        fields=[
            FieldMap(field="full_name", source="Họ và Tên", required=True),
            FieldMap(field="birth_date", source="Ngày Sinh", transforms=["date:%d/%m/%Y"]),
            FieldMap(field="id_number", source="Số CCCD", transforms=["pad_left:12"]),
            FieldMap(field="vip", const="false"),
        ],
    )
    mapper = Mapper(mapping, crm_profile)
    item = mapper.apply(Record(1, {"Họ và Tên": "", "Ngày Sinh": "31/02/1990", "Số CCCD": "1"}))
    assert set(item.errors) == {"full_name", "birth_date"}
    assert item.values["id_number"] == "000000000001"
    assert item.values["vip"] == "false"


def test_mapper_rejects_unknown_field(simple_profile: Profile) -> None:
    bad = Mapping(name="x", profile="p", fields=[FieldMap(field="nope", source="a")])
    with pytest.raises(ConfigError, match="không có trong ứng dụng đích"):
        Mapper(bad, simple_profile)


def test_mapper_rejects_empty_data_mapping(simple_profile: Profile) -> None:
    with pytest.raises(ConfigError, match="Chưa ánh xạ"):
        Mapper(Mapping(name="empty", profile=simple_profile.id, fields=[]), simple_profile)


def test_check_reports_missing_column_and_transform(simple_profile: Profile) -> None:
    m = Mapping(
        name="x", profile="p", fields=[FieldMap(field="name", source="Tên", transforms=["oops"])]
    )
    problems = Mapper.check(m, simple_profile, columns=["Other"])
    assert any("Không thấy cột 'Tên'" in p for p in problems)
    assert any("oops" in p for p in problems)


def test_suggest_is_accent_insensitive(crm_profile: Profile) -> None:
    cols = ["Ho va ten", "Ngay sinh", "SO CCCD", "Dien thoai", "Ghi chú"]
    s = suggest_mapping(cols, crm_profile)
    assert s["full_name"] == "Ho va ten"
    assert s["birth_date"] == "Ngay sinh"
    assert s["id_number"] == "SO CCCD"
    assert s["phone"] == "Dien thoai"


def test_parse_rows() -> None:
    assert parse_rows("1-3, 7") == {1, 2, 3, 7}
    assert parse_rows("") is None
    with pytest.raises(ValueError):
        parse_rows("5-2")


@pytest.mark.parametrize(
    ("values", "field", "expected"),
    [
        (["2024-01-31", "2023-12-01T00:00:00"], "birth_date", ["date:%d/%m/%Y"]),
        (["0912 345 678", "+84987654321"], "phone", ["phone_vn"]),
        (["0912 345 678"], "full_name", ["strip"]),
        (["Nguyễn  Văn A"], "full_name", ["collapse_spaces"]),
        ([], "x", ["strip"]),
    ],
)
def test_suggest_transforms_from_sample_values(values, field, expected):
    from autoinput.mapping import suggest_transforms

    assert suggest_transforms(values, field) == expected

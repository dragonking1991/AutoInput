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

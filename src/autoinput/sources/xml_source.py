from collections.abc import Iterator
from typing import Any
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET  # blocks XXE / entity-expansion attacks

from autoinput.domain import SourceError
from autoinput.sources.base import Source, source_registry


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@source_registry.register(".xml")
class XmlSource(Source):
    label = "XML"

    def _rows(self) -> Iterator[dict[str, Any]]:
        try:
            root = SafeET.parse(self.path).getroot()
        except SafeET.ParseError as e:
            raise SourceError(f"Invalid XML: {e}") from e

        tag = self.options.record_tag or self._detect_record_tag(root)
        self.log.debug(f"{self.path.name}: record tag <{tag}>")
        for elem in root.iter():
            if _local(elem.tag) == tag:
                yield self._to_row(elem)

    @staticmethod
    def _detect_record_tag(root: Element) -> str:
        children = list(root)
        if not children:
            raise SourceError("XML root has no child elements")
        return _local(children[0].tag)

    @staticmethod
    def _to_row(elem: Element) -> dict[str, Any]:
        row: dict[str, Any] = {f"@{_local(k)}": v for k, v in elem.attrib.items()}
        for child in elem:
            name = _local(child.tag)
            for k, v in child.attrib.items():
                row[f"{name}@{_local(k)}"] = v
            row[name] = (child.text or "").strip()
        return row

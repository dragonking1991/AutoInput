import csv
from collections.abc import Iterator
from typing import Any

from charset_normalizer import from_path

from autoinput.sources.base import Source, source_registry


@source_registry.register(".csv", ".tsv", ".txt")
class CsvSource(Source):
    label = "CSV / TSV"

    def encoding(self) -> str:
        if self.options.encoding:
            return self.options.encoding
        best = from_path(self.path).best()
        return best.encoding if best else "utf-8"

    def delimiter(self, sample: str) -> str:
        if self.options.delimiter:
            return self.options.delimiter
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            return "\t" if self.path.suffix.lower() == ".tsv" else ","

    def _rows(self) -> Iterator[dict[str, Any]]:
        encoding = self.encoding()
        with self.path.open(encoding=encoding, newline="", errors="replace") as f:
            sample = f.read(8192)
            f.seek(0)
            delimiter = self.delimiter(sample)
            self.log.debug(f"{self.path.name}: encoding={encoding} delimiter={delimiter!r}")
            for _ in range(self.options.header_row - 1):
                next(f, None)
            yield from csv.DictReader(f, delimiter=delimiter)

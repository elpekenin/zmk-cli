"""
YAML parser/printer which preserves any comments before the document.
"""

from collections.abc import Callable
from io import UnsupportedOperation
from pathlib import Path
from typing import Any

import ruamel.yaml

# NOTE(elpekenin): ruamel.yaml.compat.StreamType exists
# however, it is just an alias for Any and it is defined on a `if False:` block
StreamType = Any


class YAML(ruamel.yaml.YAML):
    """
    YAML handler which leaves any comments prior to the start of the document
    unchanged.

    A stream passed to dump() should be in r+ mode. If the stream is not
    readable or seekable, a leading comment will be overwritten.
    """

    def dump(
        self,
        data: Path | StreamType,
        stream: Path | StreamType | None = None,
        *,
        transform: Callable[..., Any] | None = None,
    ) -> None:
        if stream is None:
            raise TypeError("Dumping from a context manager is not supported.")

        if isinstance(stream, Path):
            with stream.open("a+", encoding="utf-8") as f:
                f.seek(0)
                self.dump(data, f, transform=transform)
                return

        try:
            if stream.readable() and stream.seekable():
                _seek_to_document_start(stream)

            stream.truncate()
        except UnsupportedOperation:
            pass

        super().dump(data, stream=stream, transform=transform)


def _seek_to_document_start(stream: StreamType) -> None:
    while True:
        line = stream.readline()
        if not line:
            break

        text, _, _ = line.partition("#")
        text = text.strip()

        if text == "---":
            # Found the start of the document, and everything before it was
            # comments and/or whitespace.
            stream.seek(stream.tell())
            return

        if text:
            # Found something that wasn't a comment or whitespace before we
            # found a document start marker. The start of the document is the
            # start of the file.
            stream.seek(0)
            return


def read_yaml(path: Path) -> Any:
    """Parse a YAML file"""
    return YAML().load(path)

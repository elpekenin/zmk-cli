"""
"zmk remove" command.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Optional

import rich
import typer
from rich.prompt import Confirm, InvalidResponse, PromptBase

from ...menu import detail_list, show_menu
from ...templates import get_template_files
from ...util import fatal_error
from ..config import Config


class KeyboardType(StrEnum):
    """The Zephyr hardware type for a keyboard."""

    SHIELD = "shield"
    BOARD = "board"


class KeyboardLayout(StrEnum):
    """The physical layout of a keyboard."""

    UNIBODY = "unibody"
    SPLIT = "split"


@dataclass
class TemplateData:
    """Data needed to read template files."""

    folder: str = ""
    dest: str = ""
    data: dict[str, str] = field(default_factory=dict)


ID_PATTERN = re.compile(r"[a-z_]\w*")
MAX_NAME_LENGTH = 16


def _validate_id(value: str):
    if not value:
        raise typer.BadParameter("ID must be at least one character long.")

    if not ID_PATTERN.fullmatch(value):
        raise typer.BadParameter(
            "Keyboard ID must use only lowercase letters, numbers, and underscores "
            "and must not start with a number."
        )


def _validate_name(name: str):
    name = name.strip()
    if not name:
        raise typer.BadParameter("Name must be at least one character long.")


def _validate_short_name(name: str):
    if not name:
        raise typer.BadParameter("Name must be at least one character long.")

    if len(name) > MAX_NAME_LENGTH:
        raise typer.BadParameter(f"Name must be <= {MAX_NAME_LENGTH} characters.")


def _id_callback(value: Optional[str]):
    if value is not None:
        _validate_id(value)


def _name_callback(name: Optional[str]):
    if name is not None:
        _validate_name(name)


def _short_name_callback(name: Optional[str]):
    if name is not None:
        _validate_short_name(name)


def keyboard_new(
    ctx: typer.Context,
    keyboard_id: Annotated[
        Optional[str],
        typer.Option("--id", "-i", help="Board/shield ID.", callback=_id_callback),
    ] = None,
    keyboard_name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Keyboard name.", callback=_name_callback),
    ] = None,
    short_name: Annotated[
        Optional[str],
        typer.Option(
            "--shortname",
            "-s",
            help=f"Abbreviated keyboard name (<= {MAX_NAME_LENGTH} characters).",
            callback=_short_name_callback,
        ),
    ] = None,
    keyboard_type: Annotated[
        Optional[KeyboardType],
        typer.Option(
            "--type",
            "-t",
            help="Type of keyboard to create.",
        ),
    ] = None,
    keyboard_layout: Annotated[
        Optional[KeyboardLayout],
        typer.Option("--layout", "-l", help="Keyboard hardware layout."),
    ] = None,
):
    """Create a new keyboard from a template."""
    cfg = ctx.find_object(Config)
    repo = cfg.get_repo()

    board_root = repo.board_root
    if not board_root:
        fatal_error('Cannot find repo\'s "boards" folder.')

    if not keyboard_name:
        keyboard_name = NamePrompt.ask()

    if not short_name:
        if len(keyboard_name) <= MAX_NAME_LENGTH:
            short_name = keyboard_name
        else:
            short_name = ShortNamePrompt.ask()

    if not keyboard_id:
        keyboard_id = IdPrompt.ask(name=short_name)

    if not keyboard_type:
        keyboard_type = _prompt_keyboard_type()

    if not keyboard_layout:
        keyboard_layout = _prompt_keyboard_layout()

    template = _get_template(
        keyboard_type,
        keyboard_layout,
        keyboard_name=keyboard_name,
        short_name=short_name,
        keyboard_id=keyboard_id,
    )

    dest: Path = board_root / template.dest

    try:
        dest.mkdir(parents=True)
    except FileExistsError as exc:
        if not Confirm.ask(
            "This keyboard already exists. Overwrite it?", default=False
        ):
            raise typer.Exit() from exc

    for name, data in get_template_files(template.folder, **template.data):
        file = dest / name
        file.write_bytes(data.encode())

    rich.print()
    rich.print(f'Files were written to "{dest}".')
    rich.print(
        "Open this folder and edit the files to finish setting up the new keyboard."
    )
    rich.print("See https://zmk.dev/docs/development/new-shield for help.")


def _prompt_keyboard_type():
    items = detail_list(
        [
            (KeyboardType.SHIELD, "A PCB which uses a separate controller board"),
            (KeyboardType.BOARD, "A standalone PCB with onboard controller"),
        ]
    )

    result = show_menu("Select a keyboard type:", items)
    return result.data


def _prompt_keyboard_layout():
    items = detail_list(
        [
            (KeyboardLayout.UNIBODY, "A keyboard with a single controller"),
            (KeyboardLayout.SPLIT, "A keyboard with separate left/right controllers"),
        ]
    )

    result = show_menu("Select a keyboard layout:", items)
    return result.data


class NamePromptBase(PromptBase[str]):
    """Base class for keyboard name prompts."""

    @classmethod
    def validate(cls, value: str) -> None:
        """:raise: typer.BadParameter if the value is invalid"""
        raise NotImplementedError()

    def process_response(self, value: str) -> str:
        value = value.strip()
        try:
            self.validate(value)
            return value
        except typer.BadParameter as exc:
            raise InvalidResponse(f"[prompt.invalid]{exc}") from exc


class NamePrompt(NamePromptBase):
    """Prompt for a keyboard name."""

    @classmethod
    def validate(cls, value: str):
        _validate_name(value)

    @classmethod
    def ask(cls):
        return super().ask("Enter the name of the keyboard")


class ShortNamePrompt(NamePromptBase):
    """Prompt for an abbreviated keyboard name."""

    @classmethod
    def validate(cls, value: str):
        _validate_short_name(value)

    @classmethod
    def ask(cls):
        return super().ask(
            f"Enter an abbreviated name [dim](<= {MAX_NAME_LENGTH} chars)"
        )


class IdPrompt(NamePromptBase):
    """Prompt for a keyboard identifier."""

    @classmethod
    def validate(cls, value: str):
        _validate_id(value)

    @classmethod
    def ask(cls, name: str):
        return super().ask(
            "Enter an ID for the keyboard", default=_get_default_id(name)
        )


def _get_template(
    keyboard_type: KeyboardType,
    keyboard_layout: KeyboardLayout,
    keyboard_name: str,
    short_name: str,
    keyboard_id: str,
):
    template = TemplateData()
    template.data["name"] = keyboard_name
    template.data["shortname"] = short_name

    match keyboard_type:
        case KeyboardType.SHIELD:
            template.data["shield"] = keyboard_id
            template.folder = "shield/"
            template.dest = f"shields/{keyboard_id}"

        case _:
            template.data["board"] = keyboard_id
            template.folder = "board/"
            template.dest = f"arm/{keyboard_id}"

    match keyboard_layout:
        case KeyboardLayout.UNIBODY:
            template.folder += "unibody"

        case KeyboardLayout.SPLIT:
            template.folder += "split"

        case _:
            raise NotImplementedError()

    return template


def _get_default_id(name: str):
    # ID must be lowercase
    result = name.strip().lower()

    # ID must contain only word characters
    result = re.sub(r"\W+", "_", result)
    result = result.strip("_")

    # ID cannot start with a number
    result = re.sub(r"^\d+_*", "", result)

    return result if result else ...
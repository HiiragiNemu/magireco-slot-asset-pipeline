#!/usr/bin/env python3
"""Shared fail-closed contract for identifier-derived output directories.

The production tools accept logical event/scene/series/collection identifiers
from command-line arguments and audited JSON.  Those values are metadata, not
paths.  This module keeps that boundary explicit and also checks the resolved
destination so an already-existing symlink cannot redirect a write outside the
declared output root.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath


class UnsafeOutputIdentifier(ValueError):
    """Raised when metadata cannot safely be used as one path component."""


_WINDOWS_RESERVED_BASENAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CLOCK$",
        "CONIN$",
        "CONOUT$",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)
_WINDOWS_INVALID_FILENAME_CHARACTERS = frozenset('<>"|?*')


def validate_output_identifier(value: object, *, label: str = "output identifier") -> str:
    """Return *value* as a safe, literal, single-component identifier.

    The same restrictions are applied on every host OS because releases are
    produced and exchanged on Windows.  In particular, a colon is always
    rejected: it can denote either a drive or an NTFS alternate data stream.
    """

    if not isinstance(value, str):
        raise UnsafeOutputIdentifier(f"{label} must be a string")
    identifier = value
    if not identifier:
        raise UnsafeOutputIdentifier(f"{label} must not be empty")
    if identifier in {".", ".."}:
        raise UnsafeOutputIdentifier(f"{label} must not be a dot path")
    if identifier.endswith((" ", ".")):
        raise UnsafeOutputIdentifier(
            f"{label} must not end in a Windows-trimmed dot or space"
        )
    if "/" in identifier or "\\" in identifier:
        raise UnsafeOutputIdentifier(f"{label} must be exactly one path component")
    if ":" in identifier:
        raise UnsafeOutputIdentifier(
            f"{label} must not contain a drive or Windows ADS separator"
        )
    if any(character in _WINDOWS_INVALID_FILENAME_CHARACTERS for character in identifier):
        raise UnsafeOutputIdentifier(
            f"{label} contains a character forbidden in Windows filenames"
        )
    if any(unicodedata.category(character) == "Cc" for character in identifier):
        raise UnsafeOutputIdentifier(f"{label} contains a control character")

    windows_path = PureWindowsPath(identifier)
    posix_path = PurePosixPath(identifier)
    if windows_path.drive or windows_path.root or windows_path.is_absolute():
        raise UnsafeOutputIdentifier(f"{label} must not be an absolute or drive path")
    if posix_path.is_absolute():
        raise UnsafeOutputIdentifier(f"{label} must not be an absolute path")

    # Windows reserves these device basenames even when an extension follows
    # (for example CON.json or LPT1.release).
    basename = identifier.split(".", 1)[0].upper()
    if basename in _WINDOWS_RESERVED_BASENAMES:
        raise UnsafeOutputIdentifier(f"{label} uses a Windows reserved device name")
    return identifier


def ensure_resolved_containment(
    root: Path,
    candidate: Path,
    *,
    label: str = "output path",
    allow_root: bool = False,
) -> Path:
    """Return *candidate* after proving its resolved path is below *root*.

    ``Path.resolve(strict=False)`` follows every existing symlink component and
    still canonicalizes a not-yet-created suffix.  This therefore rejects an
    existing child symlink that points outside the output root before callers
    create, rename, replace, or recursively remove anything.
    """

    resolved_root = Path(root).resolve(strict=False)
    resolved_candidate = Path(candidate).resolve(strict=False)
    try:
        relative = resolved_candidate.relative_to(resolved_root)
    except ValueError as error:
        raise UnsafeOutputIdentifier(
            f"{label} escapes its declared output root after resolution"
        ) from error
    if not allow_root and relative == Path("."):
        raise UnsafeOutputIdentifier(f"{label} resolves to the output root itself")
    return Path(candidate)


def resolve_output_child(
    root: Path,
    identifier: object,
    *,
    label: str = "output identifier",
) -> Path:
    """Validate one logical identifier and return its contained output path."""

    safe_identifier = validate_output_identifier(identifier, label=label)
    resolved_root = Path(root).resolve(strict=False)
    candidate = resolved_root / safe_identifier
    ensure_resolved_containment(
        resolved_root,
        candidate,
        label=f"{label} destination",
    )
    return candidate

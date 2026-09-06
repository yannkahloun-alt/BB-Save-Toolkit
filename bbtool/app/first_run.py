"""First-run local-application defaults that do not redefine durable identity."""
from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import uuid

from .user_state import PreferencesState, StateConflictError, UserStateStore


_DOCUMENTS_FOLDER_ID = uuid.UUID("fdd39ad0-238f-46af-adb4-6c85480369c7").bytes_le
_BATTLE_BROTHERS_QUICKSAVE = Path("Battle Brothers") / "savegames" / "quicksave.sav"


def resolve_windows_documents() -> Path | None:
    """Resolve the current user's Windows Documents known folder.

    The shell known-folder API follows configured redirection, including a
    OneDrive-backed Documents folder.  Other platforms have no Windows default.
    """
    if sys.platform != "win32":
        return None

    try:
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    except (AttributeError, OSError):
        return None

    folder_id = (ctypes.c_ubyte * 16).from_buffer_copy(_DOCUMENTS_FOLDER_ID)
    path_pointer = ctypes.c_void_p()

    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None

    result = shell32.SHGetKnownFolderPath(
        ctypes.cast(ctypes.byref(folder_id), ctypes.c_void_p),
        0,
        None,
        ctypes.byref(path_pointer),
    )
    if result != 0 or not path_pointer.value:
        return None

    try:
        return Path(ctypes.wstring_at(path_pointer.value))
    finally:
        ole32.CoTaskMemFree(path_pointer)


def default_battle_brothers_quicksave(documents: Path) -> Path:
    """Build the conventional quicksave path below an already-resolved Documents."""
    return Path(documents) / _BATTLE_BROTHERS_QUICKSAVE


def initialize_first_run_save_default(
    *,
    state_root: Path | None = None,
    documents_resolver: Callable[[], Path | None] = resolve_windows_documents,
) -> Path | None:
    """Persist the Windows quicksave default only for truly unconfigured state.

    A present preferences payload is authoritative even when its selected path
    is ``None`` (for example after an explicit forget/reset).  Missing or
    unavailable quicksave files are still persisted as the first-run target so
    the existing followed-save unavailable state can report them without
    guessing another save.
    """
    store = UserStateStore(state_root)
    preferences_path = store.path_for("preferences")
    if preferences_path.exists():
        current = store.load("preferences")
        return (
            Path(current.selected_save_path)
            if current.selected_save_path is not None
            else None
        )

    documents = documents_resolver()
    if documents is None:
        return None
    default_path = default_battle_brothers_quicksave(documents)

    # Loading before the first write deliberately preserves the durable-state
    # corruption/high-watermark checks; missing JSON is not silently treated as
    # first-run when revision evidence says otherwise.
    current = store.load("preferences")
    try:
        saved = store.save(
            "preferences",
            PreferencesState(
                selected_save_path=str(default_path),
                auto_refresh=current.auto_refresh,
            ),
            expected_revision=current.revision,
        )
    except StateConflictError:
        # A concurrent first writer wins.  Never overwrite a selection that
        # became authoritative between the existence check and this write.
        saved = store.load("preferences")

    return Path(saved.selected_save_path) if saved.selected_save_path is not None else None


__all__ = [
    "default_battle_brothers_quicksave",
    "initialize_first_run_save_default",
    "resolve_windows_documents",
]

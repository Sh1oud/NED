"""Opening the casebook for one request, in one place.

This is deliberately not a FastAPI dependency: a dependency and the endpoint it feeds can run on
different threadpool workers, and a sqlite connection belongs to the thread that made it. Opening
the store inside the endpoint body keeps one connection on one thread for the whole request.

It lives in its own module because two routers need it - the casebook's own routes and the review
path on ``/api/analyze`` - and the casebook router already imports from the analyse router, so
sharing the helper any other way would close an import cycle.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from ned.app.store import (
    CasebookBusyError,
    CasebookConfigError,
    CasebookCorruptError,
    CasebookNotFoundError,
    CasebookStore,
    SchemaTooNewError,
    casebook_enabled,
    casebook_path,
    open_casebook,
)


@contextmanager
def open_store() -> Iterator[CasebookStore]:
    """One store for one request, opened and closed in the request's own thread."""

    try:
        store = open_casebook()
    except SchemaTooNewError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (CasebookCorruptError, CasebookBusyError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except CasebookConfigError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    if store is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "the casebook is switched off on this machine (NED_CASEBOOK=off); "
                "nothing has been stored, and nothing can be filed or reviewed"
            ),
        )
    try:
        yield store
    finally:
        store.close()


@contextmanager
def open_store_read_only() -> Iterator[CasebookStore]:
    """Open the casebook read-only. A reread is a read, and this makes that structural.

    ``CasebookStore.open_read_only`` never migrates, never writes and refuses every write method,
    so the reread path cannot touch the archive even if a later change tried to. A file that does
    not exist yet is a 404 rather than a reason to create one.
    """

    try:
        enabled = casebook_enabled()
        path = casebook_path() if enabled else None
    except CasebookConfigError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    if not enabled or path is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "the casebook is switched off on this machine (NED_CASEBOOK=off); "
                "nothing has been stored, and nothing can be read back"
            ),
        )
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="there is no casebook file on this machine yet",
        )
    try:
        store = CasebookStore.open_read_only(path)
    except CasebookNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (CasebookCorruptError, CasebookBusyError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    try:
        yield store
    finally:
        store.close()


@contextmanager
def open_store_read_only_for_casebook(casebook_id: str) -> Iterator[CasebookStore]:
    """Read-only, and the casebook must be on file."""

    with open_store_read_only() as store:
        try:
            store.get_casebook(casebook_id)
        except CasebookNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        yield store


@contextmanager
def open_store_for_casebook(casebook_id: str) -> Iterator[CasebookStore]:
    """Open the store and prove the casebook exists, with every store failure mapped to HTTP.

    A request that names a casebook it cannot have is an error, not a silent fallback to a
    single-case analysis: answering "here is your report, no history was involved" would hide the
    fact that the review the reader asked for did not happen.
    """

    with open_store() as store:
        try:
            store.get_casebook(casebook_id)
        except CasebookNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        yield store


__all__ = [
    "open_store",
    "open_store_for_casebook",
    "open_store_read_only",
    "open_store_read_only_for_casebook",
]

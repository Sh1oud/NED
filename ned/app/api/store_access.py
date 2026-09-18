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


__all__ = ["open_store", "open_store_for_casebook"]

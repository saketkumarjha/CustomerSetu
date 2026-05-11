"""Helpers for interpreting PostgREST / Supabase client errors."""

from __future__ import annotations


def is_missing_relation_error(exc: BaseException) -> bool:
    """
    True when PostgREST reports an unknown table/view (schema cache miss).

    Happens if migrations were not applied to the Supabase project.
    """
    try:
        from postgrest.exceptions import APIError

        if isinstance(exc, APIError) and exc.code == "PGRST205":
            return True
    except ImportError:
        pass
    return False

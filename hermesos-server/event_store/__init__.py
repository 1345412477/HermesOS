try:
    from .storage import EventStore
except ImportError:
    from event_store.storage import EventStore  # type: ignore[no-redef]

__all__ = ["EventStore"]

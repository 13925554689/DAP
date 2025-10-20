"""Utility helpers for safely working with asyncio in synchronous contexts."""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional


def ensure_event_loop(
    logger: Optional[logging.Logger] = None,
) -> asyncio.AbstractEventLoop:
    """
    Ensure that the current thread has an event loop.

    Returns the running loop when available. Otherwise, creates and assigns a
    new event loop to the current thread.
    """
    try:
        loop = asyncio.get_running_loop()
        if logger:
            logger.debug("Using existing running event loop")
        return loop
    except RuntimeError:
        loop = None

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            if logger:
                logger.debug("Existing event loop is closed; creating a new one")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if logger:
        logger.debug("Event loop ready (running=%s)", loop.is_running())
    return loop


def schedule_async_task(
    coro_factory: Callable[[], Awaitable[Any]],
    logger: Optional[logging.Logger] = None,
    task_name: Optional[str] = None,
) -> Any:
    """
    Schedule an async coroutine on the current loop if one is running.
    Falls back to executing it synchronously when no loop is active.
    """
    description = task_name or getattr(coro_factory, "__name__", "async task")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        if logger:
            logger.debug("Scheduling %s on running event loop", description)
        return loop.create_task(coro_factory())

    if logger:
        logger.debug("No running event loop; executing %s synchronously", description)

    try:
        return asyncio.run(coro_factory())
    except RuntimeError:
        loop = ensure_event_loop(logger)
        return loop.run_until_complete(coro_factory())

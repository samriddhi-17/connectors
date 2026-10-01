"""Custom uvicorn loop factory.

uvicorn 0.52 hardcodes ``ProactorEventLoop`` on Windows, which psycopg's
async connections cannot use. Supplying this factory (via the ``loop=``
argument to ``uvicorn.run``) forces a selector-based loop everywhere it
matters. On Linux it is equivalent to the platform default.
"""
import asyncio
import selectors


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop(selectors.SelectSelector())
"""Simple in-process command router for the API layer.

:class:`Router` is a lightweight registry that maps string route names to
handler callables.  It is used by the CLI and tests to dispatch operations
without coupling callers to specific handler imports.
"""
from __future__ import annotations

from typing import Any, Callable

from pyservicelab.api.schemas import ApiResponse


# Handler type: any callable that accepts keyword arguments and returns ApiResponse
HandlerFn = Callable[..., ApiResponse]


class Router:
    """Registry that maps route names to handler functions.

    Usage example::

        router = Router()
        router.register("list_users", lambda **kw: handle_list_users(kw["user_service"]))
        response = router.dispatch("list_users", user_service=svc)
    """

    def __init__(self) -> None:
        self._routes: dict[str, HandlerFn] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, route: str, handler: HandlerFn) -> None:
        """Register *handler* under *route*.

        Args:
            route: Unique route identifier string.
            handler: Callable that accepts keyword arguments and returns ApiResponse.

        Raises:
            ValueError: If *route* is already registered.
        """
        if route in self._routes:
            raise ValueError(f"Route '{route}' is already registered")
        self._routes[route] = handler

    def register_many(self, routes: dict[str, HandlerFn]) -> None:
        """Register multiple routes at once."""
        for route, handler in routes.items():
            self.register(route, handler)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, route: str, **kwargs: Any) -> ApiResponse:
        """Call the handler registered for *route*, passing **kwargs**.

        Returns an error ApiResponse if the route is not found or the handler
        raises an unexpected exception.

        Args:
            route: The route identifier to dispatch to.
            **kwargs: Arguments forwarded to the handler function.

        Returns:
            :class:`~pyservicelab.api.schemas.ApiResponse` from the handler.
        """
        handler = self._routes.get(route)
        if handler is None:
            return ApiResponse.fail(f"Unknown route: '{route}'")
        try:
            return handler(**kwargs)
        except Exception as exc:  # pragma: no cover
            return ApiResponse.fail(f"Unexpected error dispatching '{route}': {exc}")

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def routes(self) -> list[str]:
        """Return a sorted list of all registered route names."""
        return sorted(self._routes.keys())

    def has_route(self, route: str) -> bool:
        """Return True if *route* is registered."""
        return route in self._routes

    def __repr__(self) -> str:
        return f"Router(routes={self.routes()})"

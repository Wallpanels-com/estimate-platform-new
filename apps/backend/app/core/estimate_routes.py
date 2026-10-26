"""Return the exact saved revision alongside every estimate mutation response."""
from fastapi.routing import APIRoute


class EstimateRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            response = await original(request)
            session = getattr(request.state, "estimate_session", None)
            estimate = session.info.get("last_estimate") if session is not None else None
            if estimate is not None and response.status_code < 400:
                response.headers["X-Estimate-ID"] = str(estimate.id)
                response.headers["X-Estimate-Revision"] = estimate.revision
            return response
        return handle

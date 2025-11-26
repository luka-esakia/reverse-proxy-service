import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from proxy.schemas import ProxyExecuteRequest
from proxy.decision_mapper import DecisionMapper
from proxy.middleware import RequestResponseLoggerMiddleware
from proxy.logging_config import audit_log, REQUEST_ID_CTX, get_request_id
from providers.openliga import OpenLigaProvider
from config import config


# Initialize FastAPI app
app = FastAPI(
    title="Generic Reverse Proxy Service",
    description="A schema-driven reverse proxy for external sports APIs",
    version="1.0.0",
)

# Add middleware for request/response logging
app.add_middleware(RequestResponseLoggerMiddleware)


# Initialize provider based on configuration
def create_provider():
    """Factory function to create provider based on config."""
    provider_config = config.get_provider_config()

    if config.provider_name == "openliga":
        return OpenLigaProvider(provider_config)
    else:
        raise ValueError(f"Unknown provider: {config.provider_name}")


# Initialize decision mapper with provider
provider = create_provider()
decision_mapper = DecisionMapper(provider)


@app.post("/proxy/execute")
async def proxy_execute(request: ProxyExecuteRequest):
    """
    Main proxy endpoint that routes operations to appropriate providers.

    Validates input, selects provider, and returns normalized response.
    """
    # Get request ID from context (set by middleware) or use provided one
    request_id = get_request_id() or request.requestId or str(uuid.uuid4())

    try:
        audit_log(
            stage="proxy_start",
            operation_type=request.operationType,
        )

        # Execute operation through decision mapper
        result = await decision_mapper.execute_operation(
            request.operationType, request.payload
        )

        # Check if result is an error
        if "error" in result:
            audit_log(
                stage="proxy_complete",
                outcome="error",
                operation_type=request.operationType,
                error_code=result.get("code"),
            )

            # Map error codes to HTTP status codes
            status_code = 400  # Default for client errors
            if result.get("code") == "UPSTREAM_ERROR":
                status_code = 502
            elif result.get("code") == "INTERNAL_ERROR":
                status_code = 500

            return JSONResponse(status_code=status_code, content=result)

        # Success case
        audit_log(
            stage="proxy_complete",
            outcome="success",
            operation_type=request.operationType,
        )

        return {
            "requestId": request_id,
            "operationType": request.operationType,
            "data": result,
        }

    except Exception as e:
        audit_log(
            stage="proxy_complete",
            outcome="error",
            operation_type=request.operationType,
            reason=f"Unhandled exception: {str(e)}",
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "requestId": request_id,
            },
        )

    finally:
        # Context cleanup is handled by middleware
        pass


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "provider": config.provider_name}


@app.get("/operations")
async def get_operations():
    """Get information about supported operations and their schemas."""
    return {
        "supported_operations": list(decision_mapper.operation_map.keys()),
        "schemas": decision_mapper.get_operation_info(),
    }


# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint not found",
            "code": "NOT_FOUND",
            "details": {"message": "Use POST /proxy/execute for operations"},
        },
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    return JSONResponse(
        status_code=405,
        content={
            "error": "Method not allowed",
            "code": "METHOD_NOT_ALLOWED",
            "details": {"message": "Use POST /proxy/execute for operations"},
        },
    )


if __name__ == "__main__":
    import uvicorn

    print(f"Starting server with configuration:\n{config}")
    uvicorn.run("main:app", host=config.host, port=config.port, reload=True)

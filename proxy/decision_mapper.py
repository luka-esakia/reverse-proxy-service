from typing import Dict, Any
from pydantic import ValidationError

from .schemas import (
    ListLeaguesPayload,
    GetLeagueMatchesPayload,
    GetTeamPayload,
    GetMatchPayload,
    ListLeaguesResponse,
    GetLeagueMatchesResponse,
    GetTeamResponse,
    GetMatchResponse,
)
from providers.base import SportsProvider
from proxy.logging_config import audit_log


class DecisionMapper:
    """Schema-driven operation router and payload validator."""

    def __init__(self, provider: SportsProvider):
        self.provider = provider

        self.operation_map = {
            "ListLeagues": {
                "payload_validator": ListLeaguesPayload,
                "provider_method": self.provider.list_leagues,
                "response_schema": ListLeaguesResponse,
                "args_mapper": lambda payload: (),  # No args needed
            },
            "GetLeagueMatches": {
                "payload_validator": GetLeagueMatchesPayload,
                "provider_method": self.provider.get_league_matches,
                "response_schema": GetLeagueMatchesResponse,
                "args_mapper": lambda payload: (
                    payload.league_shortcut,
                    payload.league_season,
                ),
            },
            "GetTeam": {
                "payload_validator": GetTeamPayload,
                "provider_method": self.provider.get_team,
                "response_schema": GetTeamResponse,
                "args_mapper": lambda payload: (payload.team_id,),
            },
            "GetMatch": {
                "payload_validator": GetMatchPayload,
                "provider_method": self.provider.get_match,
                "response_schema": GetMatchResponse,
                "args_mapper": lambda payload: (payload.match_id,),
            },
        }

    async def execute_operation(
        self, operation_type: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an operation with validation and normalization.

        Returns:
            Normalized response data or error dict
        """

        if operation_type not in self.operation_map:
            audit_log(
                stage="validation",
                outcome="fail",
                reason=f"Unknown operationType: {operation_type}",
            )
            return {
                "error": f"Unknown operationType: {operation_type}",
                "code": "UNKNOWN_OPERATION",
                "details": {"valid_operations": list(self.operation_map.keys())},
            }

        operation_config = self.operation_map[operation_type]

        try:
            validated_payload = operation_config["payload_validator"](**payload)
            audit_log(stage="validation", outcome="pass", operation_type=operation_type)
        except ValidationError as e:
            validation_errors = []
            for error in e.errors():
                validation_errors.append(
                    {
                        "field": ".".join(str(loc) for loc in error["loc"]),
                        "message": error["msg"],
                        "type": error["type"],
                    }
                )

            audit_log(
                stage="validation",
                outcome="fail",
                operation_type=operation_type,
                reason="Payload validation failed",
                errors=validation_errors,
            )

            return {
                "error": "Payload validation failed",
                "code": "VALIDATION_ERROR",
                "details": {"validation_errors": validation_errors},
            }

        args = operation_config["args_mapper"](validated_payload)

        try:
            audit_log(
                stage="provider_call",
                operation_type=operation_type,
                provider=type(self.provider).__name__,
            )

            provider_response = await operation_config["provider_method"](*args)

            audit_log(
                stage="provider_response",
                outcome="success",
                operation_type=operation_type,
            )

        except Exception as e:
            audit_log(
                stage="provider_response",
                outcome="error",
                operation_type=operation_type,
                reason=str(e),
            )

            return {
                "error": "Upstream API failed",
                "code": "UPSTREAM_ERROR",
                "details": {"message": str(e)},
            }

        try:
            normalized_response = operation_config["response_schema"](
                **provider_response
            )

            audit_log(
                stage="response_normalization",
                outcome="success",
                operation_type=operation_type,
            )

            return normalized_response.model_dump()

        except ValidationError as e:
            audit_log(
                stage="response_normalization",
                outcome="error",
                operation_type=operation_type,
                reason="Response normalization failed",
                errors=[error["msg"] for error in e.errors()],
            )

            return {
                "error": "Internal response normalization error",
                "code": "INTERNAL_ERROR",
                "details": {"message": "Provider response format unexpected"},
            }

    def get_operation_info(self) -> Dict[str, Any]:
        """Get information about supported operations and their schemas."""
        operations = {}

        for op_name, config in self.operation_map.items():
            operations[op_name] = {
                "payload_schema": config["payload_validator"].model_json_schema(),
                "response_schema": config["response_schema"].model_json_schema(),
            }

        return operations

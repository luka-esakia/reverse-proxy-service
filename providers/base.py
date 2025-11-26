from abc import ABC, abstractmethod
from typing import Dict, Any


class SportsProvider(ABC):
    """
    Provider-agnostic interface (Adapter Pattern).
    All concrete providers must implement these methods.
    """

    @abstractmethod
    async def list_leagues(self) -> Dict[str, Any]:
        """Returns a dict ready for ListLeaguesResponse normalization."""
        pass

    @abstractmethod
    async def get_league_matches(
        self, league_shortcut: str, league_season: str
    ) -> Dict[str, Any]:
        """Returns a dict ready for GetLeagueMatchesResponse normalization."""
        pass

    @abstractmethod
    async def get_team(self, team_id: int) -> Dict[str, Any]:
        """Returns a dict ready for GetTeamResponse normalization."""
        pass

    @abstractmethod
    async def get_match(self, match_id: int) -> Dict[str, Any]:
        """Returns a dict ready for GetMatchResponse normalization."""
        pass

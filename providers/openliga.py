import asyncio
import random
import time
from typing import Dict, Any, Optional, Union, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import SportsProvider
from proxy.logging_config import audit_log


class RateLimiter:
    """Simple in-memory rate limiter for per-process request limiting."""

    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a rate limit token, waiting if necessary."""
        async with self.lock:
            now = time.time()
            # Remove old requests outside the time window
            self.requests = [
                req_time
                for req_time in self.requests
                if now - req_time < self.time_window
            ]

            if len(self.requests) >= self.max_requests:
                # Wait until the oldest request expires
                sleep_time = self.time_window - (now - self.requests[0]) + 0.1
                audit_log(stage="rate_limit", action="waiting", sleep_time=sleep_time)
                await asyncio.sleep(sleep_time)
                return await self.acquire()  # Retry after waiting

            self.requests.append(now)


class OpenLigaProvider(SportsProvider):
    """OpenLiga adapter with rate limiting and exponential backoff."""

    def __init__(self, config: Dict[str, Any]):
        self.base_url = "https://api.openligadb.de"
        self.rate_limiter = RateLimiter(
            max_requests=config.get("rate_limit_requests", 10),
            time_window=config.get("rate_limit_window", 60),
        )

        # Exponential backoff config
        self.max_retries = config.get("max_retries", 3)
        self.base_delay = config.get("base_delay", 1.0)
        self.max_delay = config.get("max_delay", 30.0)
        self.backoff_multiplier = config.get("backoff_multiplier", 2.0)
        self.jitter_range = config.get("jitter_range", 0.1)

        # Setup session with retries for connection issues
        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    async def _make_request(
        self, url: str, method: str = "GET"
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Make HTTP request with rate limiting and exponential backoff."""
        await self.rate_limiter.acquire()

        for attempt in range(self.max_retries + 1):
            start_time = time.time()

            try:
                audit_log(
                    stage="upstream_request",
                    attempt=attempt + 1,
                    method=method,
                    url=url,
                )

                response = self.session.request(method, url, timeout=10)
                latency_ms = (time.time() - start_time) * 1000

                audit_log(
                    stage="upstream_response",
                    status_code=response.status_code,
                    latency_ms=round(latency_ms, 2),
                    url=url,
                )

                if response.status_code == 200:
                    return response.json()
                elif (
                    response.status_code in [429, 500, 502, 503, 504]
                    and attempt < self.max_retries
                ):
                    # Exponential backoff with jitter
                    delay = min(
                        self.base_delay * (self.backoff_multiplier**attempt),
                        self.max_delay,
                    )
                    jitter = (
                        random.uniform(-self.jitter_range, self.jitter_range) * delay
                    )
                    sleep_time = max(0, delay + jitter)

                    audit_log(
                        stage="retry_backoff",
                        attempt=attempt + 1,
                        status_code=response.status_code,
                        sleep_time=sleep_time,
                    )

                    await asyncio.sleep(sleep_time)
                    continue
                else:
                    audit_log(
                        stage="upstream_error",
                        status_code=response.status_code,
                        final_attempt=True,
                    )
                    raise Exception(
                        f"Upstream API failed with status {response.status_code}"
                    )

            except requests.exceptions.RequestException as e:
                audit_log(stage="request_exception", attempt=attempt + 1, error=str(e))

                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.backoff_multiplier**attempt),
                        self.max_delay,
                    )
                    jitter = (
                        random.uniform(-self.jitter_range, self.jitter_range) * delay
                    )
                    sleep_time = max(0, delay + jitter)

                    await asyncio.sleep(sleep_time)
                    continue
                else:
                    raise Exception(f"Upstream API request failed: {str(e)}")

        raise Exception("Max retries exceeded")

    async def list_leagues(self) -> Dict[str, Any]:
        """Get available leagues."""
        url = f"{self.base_url}/getavailableleagues"
        data = await self._make_request(url)

        leagues = []
        if isinstance(data, list):
            for league in data:
                if isinstance(league, dict):
                    leagues.append(
                        {
                            "id": league.get("leagueId", 0),
                            "name": league.get("leagueName", ""),
                            "shortcut": league.get("leagueShortcut", ""),
                            "country": league.get("country", ""),
                            "current_season": league.get("leagueSeason", ""),
                        }
                    )

        return {"leagues": leagues}

    async def get_league_matches(
        self, league_shortcut: str, league_season: str
    ) -> Dict[str, Any]:
        """Get matches for a specific league and season."""
        url = f"{self.base_url}/getmatchdata/{league_shortcut}/{league_season}"
        data = await self._make_request(url)

        matches = []
        if isinstance(data, list):
            for match in data:
                if isinstance(match, dict):
                    team_home = match.get("team1", {})
                    team_away = match.get("team2", {})

                    # Ensure team data is dict
                    if not isinstance(team_home, dict):
                        team_home = {}
                    if not isinstance(team_away, dict):
                        team_away = {}

                    # Get final score
                    final_score = {"home": 0, "away": 0, "match_status": "scheduled"}
                    match_results = match.get("matchResults", [])
                    if (
                        match_results
                        and isinstance(match_results, list)
                        and len(match_results) > 0
                    ):
                        final_result = match_results[-1]  # Last result is usually final
                        if isinstance(final_result, dict):
                            final_score = {
                                "home": final_result.get("pointsTeam1", 0),
                                "away": final_result.get("pointsTeam2", 0),
                                "match_status": (
                                    "finished"
                                    if match.get("matchIsFinished")
                                    else "in_progress"
                                ),
                            }

                    matches.append(
                        {
                            "match_id": match.get("matchID", 0),
                            "league_name": league_shortcut,
                            "match_date_time": match.get("matchDateTime", ""),
                            "team_home": {
                                "team_id": team_home.get("teamId", 0),
                                "name": team_home.get("teamName", ""),
                                "short_name": team_home.get("shortName", ""),
                                "icon_url": team_home.get("teamIconUrl"),
                            },
                            "team_away": {
                                "team_id": team_away.get("teamId", 0),
                                "name": team_away.get("teamName", ""),
                                "short_name": team_away.get("shortName", ""),
                                "icon_url": team_away.get("teamIconUrl"),
                            },
                            "final_score": final_score,
                            "is_finished": match.get("matchIsFinished", False),
                        }
                    )

        return {"matches": matches}

    async def get_team(self, team_id: int) -> Dict[str, Any]:
        """Get team details by ID."""

        # This API endpoint is only defined https://publicapi.dev/open-liga-db-api
        # but not documented in official OpenLigaDB docs so the response is always 404.

        url = f"{self.base_url}/getteam/{team_id}"
        data = await self._make_request(url)

        team = {
            "team_id": 0,
            "name": "",
            "short_name": "",
            "icon_url": None,
        }

        if isinstance(data, dict):
            team = {
                "team_id": data.get("teamId", 0),
                "name": data.get("teamName", ""),
                "short_name": data.get("shortName", ""),
                "icon_url": data.get("teamIconUrl"),
            }

        return {"team": team}

    async def get_match(self, match_id: int) -> Dict[str, Any]:
        """Get match details by ID."""
        url = f"{self.base_url}/getmatchdata/{match_id}"
        data = await self._make_request(url)

        if not data:
            raise Exception("Match not found")

        match = None
        if isinstance(data, list) and len(data) > 0:
            match = data[0]
        elif isinstance(data, dict):
            match = data

        if not match or not isinstance(match, dict):
            raise Exception("Match not found")

        team_home = match.get("team1", {})
        team_away = match.get("team2", {})

        if not isinstance(team_home, dict):
            team_home = {}
        if not isinstance(team_away, dict):
            team_away = {}

        final_score = {"home": 0, "away": 0, "match_status": "scheduled"}
        match_results = match.get("matchResults", [])
        if match_results and isinstance(match_results, list) and len(match_results) > 0:
            final_result = match_results[-1]
            if isinstance(final_result, dict):
                final_score = {
                    "home": final_result.get("pointsTeam1", 0),
                    "away": final_result.get("pointsTeam2", 0),
                    "match_status": (
                        "finished" if match.get("matchIsFinished") else "in_progress"
                    ),
                }

        match_data = {
            "match_id": match.get("matchID", 0),
            "league_name": match.get("leagueName", ""),
            "match_date_time": match.get("matchDateTime", ""),
            "team_home": {
                "team_id": team_home.get("teamId", 0),
                "name": team_home.get("teamName", ""),
                "short_name": team_home.get("shortName", ""),
                "icon_url": team_home.get("teamIconUrl"),
            },
            "team_away": {
                "team_id": team_away.get("teamId", 0),
                "name": team_away.get("teamName", ""),
                "short_name": team_away.get("shortName", ""),
                "icon_url": team_away.get("teamIconUrl"),
            },
            "final_score": final_score,
            "is_finished": match.get("matchIsFinished", False),
        }

        return {"match": match_data}

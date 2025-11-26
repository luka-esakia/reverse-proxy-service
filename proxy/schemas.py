from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Union
from datetime import datetime


class ProxyExecuteRequest(BaseModel):
    operationType: str
    payload: Dict[str, Any]
    requestId: Optional[str] = None


class ListLeaguesPayload(BaseModel):
    pass


class GetLeagueMatchesPayload(BaseModel):
    league_shortcut: str
    league_season: str


class GetTeamPayload(BaseModel):
    team_id: int


class GetMatchPayload(BaseModel):
    match_id: int


# Response Components
class LeagueSummary(BaseModel):
    id: int
    name: str
    shortcut: str
    country: str
    season: str = Field(alias="current_season")  # Use alias for cleaner output


class TeamDetail(BaseModel):
    id: int = Field(alias="team_id")
    name: str
    short_name: str
    icon_url: Optional[str] = None


class MatchScore(BaseModel):
    home: int
    away: int
    status: str = Field(alias="match_status")


class MatchDetail(BaseModel):
    id: int = Field(alias="match_id")
    league_name: str
    date_time: Union[datetime, str] = Field(alias="match_date_time")
    team_home: TeamDetail
    team_away: TeamDetail
    score: MatchScore = Field(alias="final_score")
    is_finished: bool


# Final Normalized Response Schemas


class ListLeaguesResponse(BaseModel):
    leagues: List[LeagueSummary]


class GetLeagueMatchesResponse(BaseModel):
    matches: List[MatchDetail]


class GetTeamResponse(BaseModel):
    team: TeamDetail


class GetMatchResponse(BaseModel):
    match: MatchDetail

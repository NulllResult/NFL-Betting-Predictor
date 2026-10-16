package com.bestg.betting.models

data class TestResponse(val status: String)
data class TeamStatsResponse(val team: String, val record: String?, val points_for: Int?, val points_against: Int?, val streak: String?)
data class WinLossResponse(val regular_season_record: String?, val win_percentage: Double?, val current_streak: String?, val last_5_games: List<String>?, val home_record: String?, val away_record: String?, val has_playoffs: Boolean?, val playoff_record: String?)
data class WeatherResponse(val temperature: Int?, val conditions: String?, val wind_speed: Int?, val precipitation: Int?, val city: String?, val stadium: String?, val impact: String?)
data class Injury(val player: String?, val position: String?, val injury: String?, val status: String?, val date: String?)
data class InjuriesResponse(val team: String?, val injuries: List<Injury>?)
data class NewsItem(val headline: String?, val date: String?, val description: String?, val source: String?)
data class NewsResponse(val team: String?, val news: List<NewsItem>?)
data class PlayerInfo(val id: String?, val name: String?, val position: String?, val jersey: String?, val team: String?, val injured: Boolean?)
data class PlayerSeasonStats(val passing_yards: Int?, val passing_tds: Int?, val completions: Int?, val passing_attempts: Int?, val interceptions: Int?, val qb_rating: Double?, val rushing_yards: Int?, val rushing_tds: Int?, val rushing_attempts: Int?, val receiving_yards: Int?, val receiving_tds: Int?, val receptions: Int?, val targets: Int?, val tackles: Int?, val sacks: Int?, val def_interceptions: Int?)
data class PlayerStatsResponse(val id: String?, val name: String?, val position: String?, val jersey: String?, val team: String?, val injured: Boolean?, val stats: PlayerSeasonStats?)
data class PredictionResponse(val team1: String?, val team2: String?, val team1_win_probability: Double?, val team2_win_probability: Double?, val predicted_winner: String?, val predicted_score: String?, val predicted_spread: String?, val predicted_total: Int?, val market_spread: Double?, val market_total: Double?, val market_home_prob: Double?, val edge: Double?, val confidence: Double?, val confidence_level: String?, val key_factors: List<String>?)
data class RosterResponse(val team: String?, val players: List<PlayerInfo>?)
data class LiveScore(val away: String, val home: String, val away_score: Int, val home_score: Int, val status: String, val detail: String)
data class LiveScoresResponse(val scores: List<LiveScore>)
data class UpcomingGame(val event_id: String, val home_full: String, val away_full: String, val home: String, val away: String, val home_score: Int, val away_score: Int, val status: String, val detail: String, val is_live: Boolean, val completed: Boolean?, val home_winner: Boolean?, val away_winner: Boolean?, val date: String?, val status_text: String?, val state_type: String?)
data class UpcomingGamesResponse(val games: List<UpcomingGame>, val week: Int?)
data class AccuracyResponse(val total_predictions: Int?, val correct: Int?, val accuracy: Double?)
data class LivePrediction(
    val home: String,
    val away: String,
    val home_score: Int,
    val away_score: Int,
    val clock: String,
    val home_win_probability: Double,
    val away_win_probability: Double,
    val period: Int? = null,
    val home_spread: Double? = null,
    val predicted_final_home: Int? = null,
    val predicted_final_away: Int? = null,
    val momentum: String? = null
)
data class LivePredictionResponse(val live: List<LivePrediction>)
data class OddsGame(val game: String, val provider: String, val spread: String, val over_under: Any?, val home_ml: Any?, val away_ml: Any?)
data class OddsResponse(val odds: List<OddsGame>)
data class PlayerProp(val stat: String, val line: Int, val recommendation: String)
data class PlayerPropsResponse(val player: String?, val team: String?, val props: List<PlayerProp>?)
data class PreseasonStatsResponse(val stats: PlayerSeasonStats?)

data class PredictionLogEntry(val date: String?, val team1: String?, val team2: String?, val predicted_winner: String?, val predicted_score: String?, val confidence: Double?, val actual_winner: String?, val actual_score: String?, val correct: Boolean?)
data class PredictionLogResponse(val log: List<PredictionLogEntry>?, val total: Int?)

data class MlPredictionResponse(
    val team1: String?,
    val team2: String?,
    val ml_home_probability: Double?,
    val market_home_prob: Double?,
    val blended_home_probability: Double?,
    val edge: Double?,
    val predicted_winner: String?,
    val predicted_score: String?,
    val predicted_spread: String?,
    val predicted_total: Int?,
    val market_spread: Double?,
    val market_total: Double?,
    val confidence: Double?,
    val confidence_level: String?,
    val raw_confidence: Double? = null,
    val calibrated: Boolean? = null,
    val is_no_pick: Boolean? = null,
    val game_slot: String? = null,
    val team1_win_probability: Double? = null,
    val team2_win_probability: Double? = null,
    val key_factors: List<String>? = null,
    val key_factors_detail: List<String>? = null
)

data class SimilarMatchup(
    val season: Int?,
    val week: Int?,
    val home_team: String?,
    val away_team: String?,
    val home_score: Int?,
    val away_score: Int?,
    val winner: String?,
    val margin: Int?
)

data class SimilarMatchupSummary(
    val home_wins: Int?,
    val away_wins: Int?,
    val total: Int?
)

data class SimilarMatchupsResponse(
    val similar: List<SimilarMatchup>?,
    val summary: SimilarMatchupSummary?,
    val note: String? = null
)

data class ConfidenceBucket(val accuracy: Double?, val correct: Int?, val total: Int?)

data class BacktestResponse(
    val overall: ConfidenceBucket?,
    val by_date: Map<String, ConfidenceBucket>?,
    val by_confidence: Map<String, ConfidenceBucket>?,
    val by_side: Map<String, ConfidenceBucket>?,
    val by_edge: Map<String, ConfidenceBucket>?,
    val by_divisional: Map<String, ConfidenceBucket>?
)


data class TeamsResponse(val teams: List<String>?, val count: Int?)


data class WeekAccuracy(val week: String, val total: Int, val correct: Int, val accuracy: Double)
data class AccuracyByWeekResponse(val weeks: List<WeekAccuracy>?)

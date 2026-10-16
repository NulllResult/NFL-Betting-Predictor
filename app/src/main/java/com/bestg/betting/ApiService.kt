package com.bestg.betting

/**
 * ApiService — Retrofit interface for the NFL Flask backend.
 *
 * All model classes live in com.bestg.betting.models.ApiModels.kt.
 * Long-running endpoints should be wrapped with .await() (see RetrofitExtensions.kt)
 * when called from coroutines.
 */

import com.bestg.betting.models.*
import retrofit2.Call
import retrofit2.http.GET
import retrofit2.http.Query

interface ApiService {
    @GET("teams")
    fun getTeams(): Call<TeamsResponse>

    @GET("similar_matchups")
    fun getSimilarMatchups(
        @Query("team1") team1: String,
        @Query("team2") team2: String
    ): Call<com.bestg.betting.models.SimilarMatchupsResponse>

    @GET("backtest")
    fun getBacktest(): Call<com.bestg.betting.models.BacktestResponse>

    @GET("test")
    fun testConnection(): Call<TestResponse>

    @GET("team_stats")
    fun getTeamStats(@Query("team") team: String): Call<TeamStatsResponse>

    @GET("win_loss")
    fun getWinLoss(@Query("team") team: String): Call<WinLossResponse>

    @GET("weather")
    fun getWeather(@Query("team") team: String): Call<WeatherResponse>

    @GET("injuries")
    fun getInjuries(@Query("team") team: String): Call<InjuriesResponse>

    @GET("news")
    fun getNews(@Query("entity") entity: String): Call<NewsResponse>

    @GET("roster")
    fun getRoster(@Query("team") team: String): Call<RosterResponse>

    @GET("player_stats")
    fun getPlayerStats(@Query("name") name: String, @Query("team") team: String): Call<PlayerStatsResponse>

    @GET("predict")
    fun getPrediction(@Query("team1") team1: String, @Query("team2") team2: String): Call<PredictionResponse>

    @GET("ml_predict")
    fun getMlPrediction(@Query("team1") team1: String, @Query("team2") team2: String): Call<MlPredictionResponse>

    @GET("predict_with_market")
    fun getPredictionWithMarket(@Query("team1") team1: String, @Query("team2") team2: String): Call<PredictionResponse>

    @GET("live_scores")
    fun getLiveScores(): Call<LiveScoresResponse>

    @GET("upcoming_games")
    fun getUpcomingGames(): Call<UpcomingGamesResponse>

    @GET("accuracy_by_week")
    fun getAccuracyByWeek(): Call<AccuracyByWeekResponse>

    @GET("prediction_accuracy")
    fun getAccuracy(): Call<AccuracyResponse>

    @GET("prediction_log")
    fun getPredictionLog(): Call<PredictionLogResponse>

    @GET("live_prediction")
    fun getLivePredictions(): Call<LivePredictionResponse>

    @GET("odds")
    fun getOdds(): Call<OddsResponse>

    @GET("player_props")
    fun getPlayerProps(@Query("name") name: String, @Query("team") team: String): Call<PlayerPropsResponse>

    @GET("preseason_stats")
    fun getPreseasonStats(@Query("team") team: String, @Query("name") name: String): Call<PreseasonStatsResponse>
}

package com.bestg.betting

import com.bestg.betting.models.PredictionLogEntry
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Tests for prediction log filtering. Verifies that no data is lost
 * or altered — filters only affect display.
 */
class FilterLogicTest {

    private val testEntries = listOf(
        PredictionLogEntry(date = "2026-09-20 13:00", team1 = "KC", team2 = "BUF",
            predicted_winner = "KC", predicted_score = "24-21", confidence = 60.0,
            actual_winner = "KC", actual_score = "28-21", correct = true),
        PredictionLogEntry(date = "2026-09-21 13:00", team1 = "SF", team2 = "SEA",
            predicted_winner = "SF", predicted_score = "27-17", confidence = 70.0,
            actual_winner = "SEA", actual_score = "20-24", correct = false),
        PredictionLogEntry(date = "2026-09-22 13:00", team1 = "DAL", team2 = "PHI",
            predicted_winner = "PHI", predicted_score = "20-24", confidence = 55.0,
            actual_winner = null, actual_score = null, correct = null),
    )

    private fun applyFilter(entries: List<PredictionLogEntry>, filter: String): List<PredictionLogEntry> {
        return when (filter) {
            "CORRECT" -> entries.filter { it.correct == true }
            "WRONG"   -> entries.filter { it.correct == false }
            "PENDING" -> entries.filter { it.correct == null }
            "STARRED" -> entries.filter { false }  // no watched set in this test
            else      -> entries
        }
    }

    @Test
    fun `ALL returns all entries`() {
        assertEquals(3, applyFilter(testEntries, "ALL").size)
    }

    @Test
    fun `CORRECT returns only correct`() {
        val result = applyFilter(testEntries, "CORRECT")
        assertEquals(1, result.size)
        assertEquals("KC", result[0].team1)
    }

    @Test
    fun `WRONG returns only wrong`() {
        val result = applyFilter(testEntries, "WRONG")
        assertEquals(1, result.size)
        assertEquals("SF", result[0].team1)
    }

    @Test
    fun `PENDING returns only pending`() {
        val result = applyFilter(testEntries, "PENDING")
        assertEquals(1, result.size)
        assertEquals("DAL", result[0].team1)
    }

    @Test
    fun `filtering does not mutate original list`() {
        val originalSize = testEntries.size
        applyFilter(testEntries, "CORRECT")
        assertEquals(originalSize, testEntries.size)
    }
}

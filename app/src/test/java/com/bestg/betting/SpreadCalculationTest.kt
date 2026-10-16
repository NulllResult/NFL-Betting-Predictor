package com.bestg.betting

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Tests for the predicted-spread calculation logic that appears in the
 * Android app. Ensures the spread always matches the predicted score.
 */
class SpreadCalculationTest {

    private fun calcSpread(team1: String, team2: String, score: String?): String {
        if (score == null || !score.contains("-")) return "N/A"
        val parts = score.split("-")
        val s1 = parts[0].trim().toIntOrNull() ?: 0
        val s2 = parts[1].trim().toIntOrNull() ?: 0
        val diff = s1 - s2
        return when {
            diff > 0 -> "$team1 -$diff"
            diff < 0 -> "$team2 -${-diff}"
            else -> "Pick 'Em"
        }
    }

    @Test
    fun `home team wins by 3 to spread is -3`() {
        val result = calcSpread("Kansas City Chiefs", "Buffalo Bills", "24-21")
        assertEquals("Kansas City Chiefs -3", result)
    }

    @Test
    fun `away team wins by 2 to spread is away -2`() {
        val result = calcSpread("Kansas City Chiefs", "Buffalo Bills", "19-21")
        assertEquals("Buffalo Bills -2", result)
    }

    @Test
    fun `tie to pick em`() {
        val result = calcSpread("KC", "BUF", "21-21")
        assertEquals("Pick 'Em", result)
    }

    @Test
    fun `null score to N per A`() {
        assertEquals("N/A", calcSpread("KC", "BUF", null))
    }

    @Test
    fun `malformed score with no hyphen to N per A`() {
        assertEquals("N/A", calcSpread("KC", "BUF", "no hyphen here"))
    }

    @Test
    fun `malformed numeric parse falls back to Pick Em`() {
        // Documents existing behavior: inputs with a hyphen but non-numeric
        // parts fall through to 0-0 -> Pick 'Em
        assertEquals("Pick 'Em", calcSpread("KC", "BUF", "twenty-one to twenty"))
    }

    @Test
    fun `blowout win`() {
        assertEquals("KC -42", calcSpread("KC", "BUF", "49-7"))
    }

    @Test
    fun `single digit result`() {
        assertEquals("KC -1", calcSpread("KC", "BUF", "17-16"))
    }
}

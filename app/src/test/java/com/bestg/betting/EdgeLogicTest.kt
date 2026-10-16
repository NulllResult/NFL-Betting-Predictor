package com.bestg.betting

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Tests for edge computation and interpretation.
 * Edge = ML model probability - market probability (both as home-team %)
 */
class EdgeLogicTest {

    private fun computeEdge(mlHomePct: Double?, marketHomePct: Double?): Double? {
        if (mlHomePct == null || marketHomePct == null) return null
        return mlHomePct - marketHomePct
    }

    private fun edgeReadout(edge: Double?): String {
        if (edge == null) return "N/A"
        return when {
            edge >= 5.0 -> "Strong value on the underdog side"
            edge >= 2.0 -> "Slight value identified"
            edge <= -5.0 -> "Fade the model — heavy market disagreement"
            edge <= -2.0 -> "Model and market disagree slightly"
            else -> "Model and market aligned"
        }
    }

    @Test
    fun `model 60 vs market 55 to +5 edge`() {
        val edge = computeEdge(60.0, 55.0)
        assertEquals(5.0, edge!!, 0.001)
    }

    @Test
    fun `model 40 vs market 50 to -10 edge`() {
        val edge = computeEdge(40.0, 50.0)
        assertEquals(-10.0, edge!!, 0.001)
    }

    @Test
    fun `null ml to null edge`() {
        assertEquals(null, computeEdge(null, 55.0))
    }

    @Test
    fun `null market to null edge`() {
        assertEquals(null, computeEdge(60.0, null))
    }

    @Test
    fun `strong value readout`() {
        assertEquals("Strong value on the underdog side", edgeReadout(6.0))
    }

    @Test
    fun `fade model readout`() {
        assertEquals("Fade the model — heavy market disagreement", edgeReadout(-7.5))
    }

    @Test
    fun `aligned readout`() {
        assertEquals("Model and market aligned", edgeReadout(0.5))
    }
}

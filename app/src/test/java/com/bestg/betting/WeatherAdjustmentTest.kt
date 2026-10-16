package com.bestg.betting

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Tests the weather point-adjustment logic. Verifies severity ordering.
 * (Mirrors weather_point_adjustment in betting_api.py)
 */
class WeatherAdjustmentTest {

    private fun weatherAdj(wind: Int?, temp: Int?, precip: Int?): Double {
        var adj = 0.0
        val w = wind ?: 0
        val t = temp ?: 70
        val p = precip ?: 0

        adj += when {
            w >= 25 -> -6.0
            w >= 20 -> -4.0
            w >= 15 -> -2.5
            w >= 10 -> -1.0
            else -> 0.0
        }
        adj += when {
            t <= 15 -> -4.0
            t <= 25 -> -2.5
            t <= 35 -> -1.0
            else -> 0.0
        }
        adj += when {
            p >= 70 -> -3.0
            p >= 50 -> -1.5
            else -> 0.0
        }
        return adj
    }

    @Test
    fun `calm weather to no adjustment`() {
        assertEquals(0.0, weatherAdj(5, 70, 0), 0.001)
    }

    @Test
    fun `high wind to negative adjustment`() {
        assertTrue(weatherAdj(25, 70, 0) <= -6.0)
    }

    @Test
    fun `freezing temp to negative adjustment`() {
        assertTrue(weatherAdj(5, 10, 0) <= -4.0)
    }

    @Test
    fun `heavy rain to negative adjustment`() {
        assertTrue(weatherAdj(5, 70, 80) <= -3.0)
    }

    @Test
    fun `worst case stacks all penalties`() {
        val adj = weatherAdj(30, 10, 90)
        assertTrue(adj <= -13.0)
    }
}

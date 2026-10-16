package com.bestg.betting

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val textView = TextView(this)
        textView.text = "✅ BUILD SUCCESS!"
        textView.textSize = 24f
        
        setContentView(textView)
    }
}

# prediction_api.py - Simple Flask API for predictions
from flask import Flask, request, jsonify
import joblib
import pandas as pd
import numpy as np

app = Flask(__name__)

# Load model on startup
try:
    model = joblib.load('ml_models/random_forest.pkl')
    print("✓ Model loaded successfully")
except Exception as e:
    print(f"✗ Error loading model: {e}")
    model = None

@app.route('/predict', methods=['POST'])
def predict():
    """Predict NFL game outcome"""
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500
    
    try:
        data = request.get_json()
        
        # Extract features
        features = pd.DataFrame([{
            'home_strength': float(data.get('home_strength', 50)),
            'away_strength': float(data.get('away_strength', 50)),
            'strength_diff': float(data.get('home_strength', 50)) - float(data.get('away_strength', 50)),
            'home_yards': float(data.get('home_yards', 350)),
            'away_yards': float(data.get('away_yards', 330))
        }])
        
        # Make prediction
        probability = model.predict_proba(features)[0][1]
        
        # Determine confidence level
        confidence = "HIGH" if abs(probability - 0.5) > 0.3 else "MEDIUM" if abs(probability - 0.5) > 0.1 else "LOW"
        
        return jsonify({
            'prediction': 'HOME_WIN' if probability > 0.5 else 'AWAY_WIN',
            'probability': float(probability),
            'confidence': confidence,
            'recommended_bet': confidence in ['HIGH', 'MEDIUM'],
            'edge': abs(probability - 0.5)  # Betting edge
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'endpoints': ['/predict', '/health']
    })

if __name__ == '__main__':
    print("Starting NFL Prediction API...")
    print("Endpoint: http://localhost:5000/predict")
    print("Example: curl -X POST http://localhost:5000/predict -H 'Content-Type: application/json' -d '{\"home_strength\":65,\"away_strength\":45}'")
    app.run(debug=True, host='0.0.0.0', port=5000)

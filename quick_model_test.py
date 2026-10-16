# quick_model_test.py
import os
import joblib
import pandas as pd
import numpy as np

print("=" * 70)
print("QUICK MODEL TEST - Verify Everything Works")
print("=" * 70)

# Check current directory
current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

# Check if ml_models exists
ml_path = os.path.join(current_dir, 'ml_models')
if os.path.exists(ml_path):
    print(f"✓ ml_models directory found at: {ml_path}")
    
    # List all models
    models = []
    for file in os.listdir(ml_path):
        if file.endswith('.pkl') or file.endswith('.h5'):
            models.append(file)
    
    print(f"✓ Found {len(models)} ML models:")
    for model in sorted(models):
        size = os.path.getsize(os.path.join(ml_path, model))
        print(f"  - {model} ({size:,} bytes)")
    
    # Try to load and test a model
    try:
        rf_model = joblib.load(os.path.join(ml_path, 'random_forest.pkl'))
        print(f"\n✓ Successfully loaded random_forest.pkl")
        
        # Make a test prediction
        test_data = pd.DataFrame([{
            'home_strength': 65.0,
            'away_strength': 45.0,
            'strength_diff': 20.0,
            'home_yards': 380.0,
            'away_yards': 310.0
        }])
        
        probability = rf_model.predict_proba(test_data)[0][1]
        prediction = "HOME WIN" if probability > 0.5 else "AWAY WIN"
        
        print(f"✓ Test prediction: {prediction}")
        print(f"✓ Probability: {probability:.1%}")
        print(f"✓ Confidence: {'HIGH' if abs(probability-0.5)>0.3 else 'MEDIUM' if abs(probability-0.5)>0.1 else 'LOW'}")
        
        # Check if this would be a bet
        if abs(probability - 0.5) > 0.05:
            print(f"✓ RECOMMENDATION: BET ON {prediction}")
            print(f"✓ Expected edge: {abs(probability-0.5):.1%}")
        else:
            print(f"✓ RECOMMENDATION: NO BET (edge too small)")
            
    except Exception as e:
        print(f"✗ Error loading model: {e}")
        
else:
    print(f"✗ ERROR: ml_models directory not found!")
    print(f"  Expected at: {ml_path}")
    print(f"  Please run from: C:\\Users\\Bestg\\betting_pc_project")

print("\n" + "=" * 70)
print("NEXT STEP: Run the betting simulator")
print("Command: python betting_simulator_fixed.py")
print("=" * 70)

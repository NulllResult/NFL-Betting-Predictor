import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
import os

print("Loading data...")
df = pd.read_csv('nfl_advanced_games_v4.csv')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

# Features — all the real signal columns
feature_cols = [
    'home_off_epa', 'away_off_epa',
    'home_def_epa_allowed', 'away_def_epa_allowed',
    'home_success', 'away_success',
    'home_def_success_allowed', 'away_def_success_allowed',
    'home_turnovers', 'away_turnovers',
    'home_takeaways', 'away_takeaways',
    'home_rz_eff', 'away_rz_eff',
    'home_3d_rate', 'away_3d_rate',
    'home_sack_rate', 'away_sack_rate',
    'home_explosive_rate', 'away_explosive_rate',
    'home_pts_per_drive', 'away_pts_per_drive',
]

# Turn into differential features (home - away) to reduce dimensionality
for col in feature_cols[:]:
    if col.startswith('home_'):
        away_col = col.replace('home_', 'away_')
        if away_col in df.columns:
            diff_col = col.replace('home_', '') + '_diff'
            df[diff_col] = df[col] - df[away_col]

diff_features = [c for c in df.columns if c.endswith('_diff')]
print(f"Differential features: {len(diff_features)}")

# Add raw features too — model can use both
all_features = feature_cols + diff_features
all_features = [c for c in all_features if c in df.columns]

# Target
df['y'] = df['home_win'].astype(int)

# Time-based split
train_df = df[df['season'] <= 2023].copy()
val_df = df[df['season'] == 2024].copy()
test_df = df[df['season'].isin([2025, 2026])].copy()

print(f"\nTrain: {len(train_df)} games (2021-2023)")
print(f"Val:   {len(val_df)} games (2024)")
print(f"Test:  {len(test_df)} games (2025-2026)")

X_train = train_df[all_features].fillna(0).values
y_train = train_df['y'].values
X_val = val_df[all_features].fillna(0).values
y_val = val_df['y'].values
X_test = test_df[all_features].fillna(0).values
y_test = test_df['y'].values

# ────────── MODELS ──────────
print("\n" + "=" * 60)
print("Training models...")
print("=" * 60)

models = {}

print("\n[1] RandomForest")
rf = RandomForestClassifier(
    n_estimators=300, max_depth=8, min_samples_leaf=10,
    random_state=42, n_jobs=-1
)
rf.fit(X_train, y_train)
models['rf'] = rf
print(f"  Train acc: {accuracy_score(y_train, rf.predict(X_train)):.3f}")
print(f"  Val acc:   {accuracy_score(y_val, rf.predict(X_val)):.3f}")
print(f"  Test acc:  {accuracy_score(y_test, rf.predict(X_test)):.3f}")

print("\n[2] GradientBoosting")
gb = GradientBoostingClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    min_samples_leaf=10, random_state=42
)
gb.fit(X_train, y_train)
models['gb'] = gb
print(f"  Train acc: {accuracy_score(y_train, gb.predict(X_train)):.3f}")
print(f"  Val acc:   {accuracy_score(y_val, gb.predict(X_val)):.3f}")
print(f"  Test acc:  {accuracy_score(y_test, gb.predict(X_test)):.3f}")

print("\n[3] LogisticRegression (baseline)")
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_val_s = scaler.transform(X_val)
X_test_s = scaler.transform(X_test)
lr = LogisticRegression(max_iter=2000, C=0.5, random_state=42)
lr.fit(X_train_s, y_train)
models['lr'] = lr
print(f"  Train acc: {accuracy_score(y_train, lr.predict(X_train_s)):.3f}")
print(f"  Val acc:   {accuracy_score(y_val, lr.predict(X_val_s)):.3f}")
print(f"  Test acc:  {accuracy_score(y_test, lr.predict(X_test_s)):.3f}")

# ────────── ENSEMBLE ──────────
print("\n" + "=" * 60)
print("Ensemble (average of 3 models)")
print("=" * 60)

def ensemble_proba(X, X_s):
    p_rf = rf.predict_proba(X)[:, 1]
    p_gb = gb.predict_proba(X)[:, 1]
    p_lr = lr.predict_proba(X_s)[:, 1]
    return (p_rf + p_gb + p_lr) / 3.0

p_val = ensemble_proba(X_val, X_val_s)
p_test = ensemble_proba(X_test, X_test_s)
p_train = ensemble_proba(X_train, X_train_s)

ens_train_acc = accuracy_score(y_train, (p_train > 0.5).astype(int))
ens_val_acc = accuracy_score(y_val, (p_val > 0.5).astype(int))
ens_test_acc = accuracy_score(y_test, (p_test > 0.5).astype(int))

print(f"  Train acc: {ens_train_acc:.3f}")
print(f"  Val acc:   {ens_val_acc:.3f}")
print(f"  Test acc:  {ens_test_acc:.3f}")

print(f"\n  Train log loss: {log_loss(y_train, p_train):.4f}")
print(f"  Val log loss:   {log_loss(y_val, p_val):.4f}")
print(f"  Test log loss:  {log_loss(y_test, p_test):.4f}")

print(f"\n  Test Brier score: {brier_score_loss(y_test, p_test):.4f}")

# Accuracy at confidence thresholds (Test set)
print("\n" + "=" * 60)
print("Accuracy by confidence bucket (Test)")
print("=" * 60)
test_preds = test_df.copy()
test_preds['proba'] = p_test
test_preds['conf'] = (test_preds['proba'] - 0.5).abs() * 200  # 0-100 scale
test_preds['correct'] = (test_preds['proba'] > 0.5).astype(int) == test_preds['y']

buckets = [(0, 10), (10, 20), (20, 30), (30, 50), (50, 100)]
for lo, hi in buckets:
    sub = test_preds[(test_preds['conf'] >= lo) & (test_preds['conf'] < hi)]
    if len(sub) > 0:
        acc = sub['correct'].mean()
        print(f"  Conf {lo:3d}-{hi:3d}: {acc*100:.1f}% ({len(sub)} games)")

# ────────── FEATURE IMPORTANCE ──────────
print("\n" + "=" * 60)
print("Top 15 features (RandomForest)")
print("=" * 60)
importances = rf.feature_importances_
indices = np.argsort(importances)[::-1]
for i in range(min(15, len(all_features))):
    idx = indices[i]
    print(f"  {all_features[idx]:40s} {importances[idx]:.4f}")

# ────────── SAVE ──────────
print("\n" + "=" * 60)
print("Saving models...")
print("=" * 60)

os.makedirs('ml_models', exist_ok=True)

joblib.dump(rf, 'ml_models/random_forest_v4.pkl')
joblib.dump(gb, 'ml_models/gradient_boosting_v4.pkl')
joblib.dump(lr, 'ml_models/logistic_v4.pkl')
joblib.dump(scaler, 'ml_models/scaler_v4.pkl')
joblib.dump(all_features, 'ml_models/feature_cols_v4.pkl')

print("✅ Saved:")
print("  ml_models/random_forest_v4.pkl")
print("  ml_models/gradient_boosting_v4.pkl")
print("  ml_models/logistic_v4.pkl")
print("  ml_models/scaler_v4.pkl")
print("  ml_models/feature_cols_v4.pkl")

print(f"\n✅ FINAL TEST ACCURACY: {ens_test_acc*100:.1f}%")

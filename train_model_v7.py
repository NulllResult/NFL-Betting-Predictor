import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
from sklearn.preprocessing import StandardScaler
import os

print("Loading leakage-free data...")
df = pd.read_csv('nfl_advanced_games_v7.csv')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

# Auto-detect all feature columns from the CSV
feature_cols = [col for col in df.columns if col.endswith('_r4')]
print(f"Auto-detected {len(feature_cols)} feature columns")

# Add differentials
for col in feature_cols[:]:
    if col.startswith('home_'):
        away_col = col.replace('home_', 'away_')
        if away_col in df.columns:
            diff_col = col.replace('home_', '') + '_diff'
            df[diff_col] = df[col] - df[away_col]

diff_features = [c for c in df.columns if c.endswith('_diff')]
all_features = feature_cols + diff_features
all_features = [c for c in all_features if c in df.columns]
print(f"Total features: {len(all_features)}")

df['y'] = df['home_win'].astype(int)

# Time-based split (no shuffle!)
train_df = df[df['season'] <= 2023].copy()
val_df = df[df['season'] == 2024].copy()
test_df = df[df['season'].isin([2025, 2026])].copy()

print(f"\nTrain: {len(train_df)} (2021-2023)")
print(f"Val:   {len(val_df)} (2024)")
print(f"Test:  {len(test_df)} (2025-2026)")

X_train = train_df[all_features].fillna(0).values
y_train = train_df['y'].values
X_val = val_df[all_features].fillna(0).values
y_val = val_df['y'].values
X_test = test_df[all_features].fillna(0).values
y_test = test_df['y'].values

print("\n" + "=" * 60)
print("Training models...")
print("=" * 60)

print("\n[1] RandomForest")
rf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=20, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
print(f"  Train: {accuracy_score(y_train, rf.predict(X_train)):.3f}")
print(f"  Val:   {accuracy_score(y_val, rf.predict(X_val)):.3f}")
print(f"  Test:  {accuracy_score(y_test, rf.predict(X_test)):.3f}")

print("\n[2] GradientBoosting")
gb = GradientBoostingClassifier(n_estimators=150, max_depth=3, learning_rate=0.05, min_samples_leaf=20, random_state=42)
gb.fit(X_train, y_train)
print(f"  Train: {accuracy_score(y_train, gb.predict(X_train)):.3f}")
print(f"  Val:   {accuracy_score(y_val, gb.predict(X_val)):.3f}")
print(f"  Test:  {accuracy_score(y_test, gb.predict(X_test)):.3f}")

print("\n[3] LogisticRegression")
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_val_s = scaler.transform(X_val)
X_test_s = scaler.transform(X_test)
lr = LogisticRegression(max_iter=2000, C=0.5, random_state=42)
lr.fit(X_train_s, y_train)
print(f"  Train: {accuracy_score(y_train, lr.predict(X_train_s)):.3f}")
print(f"  Val:   {accuracy_score(y_val, lr.predict(X_val_s)):.3f}")
print(f"  Test:  {accuracy_score(y_test, lr.predict(X_test_s)):.3f}")

print("\n" + "=" * 60)
print("Ensemble (weighted average)")
print("=" * 60)

def ens_proba(X, X_s, w_rf=0.4, w_gb=0.4, w_lr=0.2):
    p_rf = rf.predict_proba(X)[:, 1]
    p_gb = gb.predict_proba(X)[:, 1]
    p_lr = lr.predict_proba(X_s)[:, 1]
    return w_rf * p_rf + w_gb * p_gb + w_lr * p_lr

p_val = ens_proba(X_val, X_val_s)
p_test = ens_proba(X_test, X_test_s)
p_train = ens_proba(X_train, X_train_s)

print(f"  Train: {accuracy_score(y_train, (p_train > 0.5).astype(int)):.3f}")
print(f"  Val:   {accuracy_score(y_val, (p_val > 0.5).astype(int)):.3f}")
print(f"  Test:  {accuracy_score(y_test, (p_test > 0.5).astype(int)):.3f}")

print(f"\n  Test log loss:   {log_loss(y_test, p_test):.4f}")
print(f"  Test Brier:      {brier_score_loss(y_test, p_test):.4f}")

print("\n" + "=" * 60)
print("Accuracy by confidence (Test)")
print("=" * 60)
tp = test_df.copy()
tp['proba'] = p_test
tp['conf'] = (tp['proba'] - 0.5).abs() * 200
tp['pred_correct'] = ((tp['proba'] > 0.5).astype(int) == tp['y'])
for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 50), (50, 100)]:
    sub = tp[(tp['conf'] >= lo) & (tp['conf'] < hi)]
    if len(sub) > 0:
        print(f"  Conf {lo:3d}-{hi:3d}: {sub['pred_correct'].mean()*100:.1f}% ({len(sub)} games)")

print("\n" + "=" * 60)
print("Top 10 features")
print("=" * 60)
importances = rf.feature_importances_
indices = np.argsort(importances)[::-1]
for i in range(min(10, len(all_features))):
    idx = indices[i]
    print(f"  {all_features[idx]:35s} {importances[idx]:.4f}")

os.makedirs('ml_models', exist_ok=True)
joblib.dump(rf, 'ml_models/random_forest_v7.pkl')
joblib.dump(gb, 'ml_models/gradient_boosting_v7.pkl')
joblib.dump(lr, 'ml_models/logistic_v7.pkl')
joblib.dump(scaler, 'ml_models/scaler_v7.pkl')
joblib.dump(all_features, 'ml_models/feature_cols_v7.pkl')

print("\n✅ Saved v5 models to ml_models/")
print(f"\n✅ FINAL TEST ACCURACY: {accuracy_score(y_test, (p_test > 0.5).astype(int))*100:.1f}%")

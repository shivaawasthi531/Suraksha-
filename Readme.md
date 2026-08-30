# Suraksha Shield

Scam call detection app built for SIH. Detects fraud calls in real time using a hybrid ML + rule-based + LLM risk engine.

## Tech Stack

- **Frontend:** React Native / Capacitor Android app (Java native modules)
  - `CallRecorderPlugin.java` — call audio capture
  - `VoskSttPlugin.java` — on-device speech-to-text (Vosk model bundled in app)
- **Backend:** FastAPI + SQLAlchemy
  - Routers: call, history, emergency, health
  - ML risk model loaded as a singleton at API startup
- **Privacy:** Metadata-only sent to admin, no raw audio stored, only unknown numbers are analyzed

## ML Model

**TF-IDF + Logistic Regression** (scikit-learn), confirmed from `train_model.py`.

**TF-IDF Vectorizer**
| Param | Value | Purpose |
|---|---|---|
| `ngram_range` | (1, 3) | captures phrases like "digital arrest warrant" as a unit |
| `max_features` | 8000 | top informative terms |
| `sublinear_tf` | True | dampens repeated-word inflation |
| `min_df` | 1 | term needs ≥1 doc to be included |

**Logistic Regression**
| Param | Value | Purpose |
|---|---|---|
| `C` | 2.0 | moderate regularization |
| `class_weight` | balanced | handles class imbalance |
| `solver` | lbfgs, multinomial | 4-class probability output |
| `max_iter` | 1000 | ensures convergence |
| `random_state` | 42 | reproducibility |

**Why this combo:** works well on small datasets (~550 samples), outputs calibrated probabilities via `predict_proba()`, n-grams catch structured scam phrasing, and it's fast enough for live call analysis.

**Training data:** `dataset_fixed.csv` (`trigger_phrase` + `scam_pattern` + `keywords_detected` → single text feature). Labels: `urgency_level` → Low=0, Medium=1, High=2, Critical=3. 80/20 stratified split + 5-fold CV. Artifacts: `scam_classifier.pkl`, `vectorizer.pkl`, `label_encoder.pkl`.

## Risk Engine

Three independent signals per call segment, blended into one score:

1. **ML score** (0–100) — TF-IDF + LogReg classifier
2. **Keyword-boost score** (0–100) — rule-based scan for known fraud phrases ("CBI", "digital arrest", "OTP", "settlement amount")
3. **LLM second opinion score** (0–100) — independent LLM review, catches phrasing the ML model hasn't seen

**Blending formula**
```
ml_kw_score = (ml_score × 0.65) + (keyword_score × 0.35)

# then, depending on mode:
final_score = max(ml_kw_score, llm_score)                        # "max" mode
final_score = (ml_kw_score × (1 − w)) + (llm_score × w)           # "weighted" mode
```

**Risk levels**
| Score | Level |
|---|---|
| 0–29 | Low |
| 30–59 | Medium |
| 60–79 | High |
| 80–100 | Critical |

Alert fires only when the final blended score crosses `ALERT_THRESHOLD` (currently **60**).

## Known Issue — Alert Threshold Gap

A confident high-risk ML prediction can still fail to trigger an alert if no exact keyword matches exist.

**Example:** Input `"I am from the customs department..."` → ML confidence 76.98% (High), but no keyword match → `keyword_score = 0`.

```
ml_kw_score = (76.98 × 0.65) + (0 × 0.35) = 50.0   # → Medium, below alert threshold
```

**Root cause:** the fixed 0.65/0.35 split zeroes out ML confidence when keywords don't match, and the LLM layer's blend weight doesn't compensate enough.

**Suggested fixes:**
- Give ML score a floor contribution when `ml_available` is true and class is already High/Critical, instead of always applying the fixed split
- Treat high-confidence ML predictions (>~75%) as an independent trigger condition
- Increase the LLM blend weight specifically when `keyword_score = 0`

## API Response Shape

Each analysis call returns:

```
risk_score          final blended score (0–100)
risk_level          Low / Medium / High / Critical
alert_triggered     bool
detected_keywords   list of matched phrases
keyword_boost       raw keyword score pre-scaling
ml_risk_score       raw ML confidence (0–100)
ml_class            predicted class label
ml_available        bool
probabilities       full 4-class probability distribution
llm_risk_score      LLM's independent score
llm_reasoning       short LLM explanation
llm_available       bool
```

## Test Coverage

- Text cleaning: lowercasing, currency symbol stripping, punctuation removal
- Keyword detection: correctly flags critical phrases ("CBI", "digital arrest"), zero boost on non-scam text
- Risk level mapping: numeric score → correct band
- End-to-end: CBI impersonation + digital arrest + settlement demand script scores >50, High/Critical, keywords detected
- Edge case: empty input → zero score, Low, no alert (no error)

---
*Architecture confirmed via source review: `train_model.py`, `model_loader.py`, `risk_engine.py`, `test_predict.py`.*

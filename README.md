Here is a **clean, professional README.md** for your project, combining:

* your **report (ML-guided cut filtering)**
* expected **assignment requirements**
* and a **production-style ML + systems documentation structure**

You can directly copy this into your repo.

---

# 🚀 ML-Guided ASIC Technology Mapping (ABC Integration)

## 📌 Overview

This project introduces a **Machine Learning–guided cut selection strategy** for ASIC technology mapping using the ABC synthesis framework. The goal is to **reduce the number of candidate cuts during mapping** while preserving **area-delay Quality of Results (QoR)**.

Traditional ABC mapping relies on **static heuristics (dominance + cut-size limits)**, which:

* Retain many low-quality cuts
* Increase runtime due to exponential candidate growth

This project replaces those heuristics with a **data-driven ML model** that dynamically predicts cut quality and prunes suboptimal candidates during mapping.

---

## 🎯 Key Contributions

* 🔍 **ML-based cut filtering inside ABC mapper (C-level integration)**
* ⚡ **Up to ~53% reduction in candidate cuts**
* 📉 **Maintains QoR parity (~0.003% deviation)**
* 🧠 Lightweight **Random Forest model transpiled to C**
* ⚙️ Fully integrated into ABC runtime (no external dependencies)

---

## 🧠 Core Idea

Instead of evaluating all possible cuts:

> Use ML to predict whether a cut is **worth exploring** before expensive mapping steps.

Each candidate cut is classified into:

* ❌ Poor → Discard immediately
* ⚠️ Average → Conditional use
* ✅ Good → Always keep

---

## 🏗️ System Architecture

```
ABC Mapper Flow
      │
      ▼
Cut Enumeration (baseline)
      │
      ▼
Feature Extraction (9 features per cut)
      │
      ▼
ML Inference (Random Forest → C code)
      │
      ▼
Cut Filtering (remove poor cuts)
      │
      ▼
Reduced Candidate Set
      │
      ▼
Delay + Area Optimization
```

---

## ⚙️ ML Model Details

### Model Type

* **Random Forest Classifier (15 trees)**

### Why Random Forest?

* Fast inference (just `if-else` branches)
* Easily transpiled into C
* No runtime dependencies
* Suitable for **millions of evaluations**

### Input Features (per cut)

* Number of leaves (**most important**)
* Max/avg logic depth
* Fanout statistics
* Truth table characteristics
* Structural metrics

### Output

* 3-class classification:

  * `0 → Poor`
  * `1 → Average`
  * `2 → Good`

---

## 📊 Training Pipeline

### Dataset

* ~3.7 million cuts from ~297 circuits

### Labels

Synthetic labels derived from:

* Dominance heuristic
* Cut size threshold
* Random balancing (to avoid bias)

### Training

* Framework: **Python (scikit-learn)**
* Class imbalance handled via:

  * `class_weight = balanced`

### Model Export

* Trained model → **transpiled into C header (`ml_inference.h`)**
* Each tree → nested `if-else` logic

---

## 🔧 Integration into ABC

### Modified Components

* `mapperCut.c` → ML-based filtering
* `mapperCore.c` → runtime mode control
* `ml_cut.c / ml_cut.h` → inference wrapper
* `ml_inference.h` → transpiled RF model

### Execution Modes

| Mode | Description            |
| ---- | ---------------------- |
| 0    | Baseline (no ML)       |
| 1    | Conservative filtering |
| 2    | Balanced filtering     |
| 3    | Aggressive filtering   |

Set using:

```bash
export ML_MODE=2
```

---

## 📈 Results

### 🔹 Cut Reduction

| Mode | Reduction |
| ---- | --------- |
| 1    | ~31%      |
| 2    | ~41%      |
| 3    | ~53%      |

---

### 🔹 CPU Time Behavior

* Total runtime: **~1.15× slower** (due to ML inference)
* Post-filter mapping: **~0.96× faster**

👉 Insight:

* ML adds **front-end overhead**
* But reduces **back-end complexity**

---

### 🔹 QoR (Area/Delay)

* ~97.6% cases → **no change**
* Average degradation: **~0.003%**
* Some cases even show **improvement**

---

## 🧪 How to Run

### 1. Clone ABC + Project

```bash
git clone https://github.com/AYUSHSHARMA9817/abc-ml-project.git
cd abc-ml-project
```

### 2. Build

```bash
make
```

### 3. Run Mapping

```bash
export ML_MODE=2   # choose mode (0–3)
./abc -c "read_blif <file>; map; print_stats"
```

---

## 📂 Project Structure

```
├── src/
│   ├── mapperCut.c        # ML filtering logic
│   ├── mapperCore.c       # mode control
│   ├── ml_cut.c/h         # inference bridge
│   └── ml_inference.h     # transpiled RF model
│
├── scripts/
│   ├── train_model.py     # ML training
│   ├── run_experiments.sh # benchmarking
│   └── plot_aggregate.py  # visualization
│
├── data/
│   ├── cuts_all_features.csv
│   └── cuts_survivors.csv
│
└── results/
    ├── logs/
    └── plots/
```

---

## 🔍 Technical Insights

### Why ML Works Here

* Mapping cost is dominated by **search space size**
* Many cuts are structurally valid but **useless**
* ML learns **hidden structural patterns** beyond heuristics

---

### Trade-off Analysis

| Aspect      | Baseline | ML-Based        |
| ----------- | -------- | --------------- |
| Cut Count   | High     | Low             |
| CPU Time    | Lower    | Slightly Higher |
| QoR         | Optimal  | Same            |
| Scalability | Limited  | Better          |

---

## ⚠️ Limitations

* Synthetic labels (not true optimal mapping outcomes)
* Slight runtime overhead
* Gains more visible on **large circuits (>100K nodes)**

---

## 🚀 Future Work

* Replace synthetic labels with **true optimal labels**
* Use **graph neural networks (GNNs)** for richer features
* Adaptive thresholds per circuit
* Evaluate on **industrial-scale designs**

---

## 🤝 Contributing

Feel free to:

* Improve model accuracy
* Optimize inference speed
* Extend feature engineering

---
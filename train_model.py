import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import _tree
from sklearn.metrics import classification_report

def tree_to_c(tree, feature_names, tree_index, f, n_classes=3):
    tree_ = tree.tree_
    feature_name = [
        feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
        for i in tree_.feature
    ]
    f.write(f"static void tree_{tree_index}_predict(float* features, float* out_probs) {{\n")
    
    def recurse(node, depth):
        indent = "  " * (depth + 1)
        if tree_.feature[node] != _tree.TREE_UNDEFINED:
            name = feature_name[node]
            threshold = tree_.threshold[node]
            feat_idx = feature_names.index(name)
            f.write(f"{indent}if (features[{feat_idx}] <= {threshold}f) {{\n")
            recurse(tree_.children_left[node], depth + 1)
            f.write(f"{indent}}} else {{\n")
            recurse(tree_.children_right[node], depth + 1)
            f.write(f"{indent}}}\n")
        else:
            value = tree_.value[node][0]
            # Ensure we don't crash if some classes are missing in this leaf
            probs = np.zeros(n_classes)
            if np.sum(value) > 0:
                # the tree indices match the actual classes present during fit
                # for a random forest fit on 0, 1, 2, value has shape (n_classes,)
                for c in range(min(n_classes, len(value))):
                    probs[c] = value[c] / np.sum(value)
            
            for c in range(n_classes):
                f.write(f"{indent}out_probs[{c}] += {probs[c]}f;\n")

    recurse(0, 1)
    f.write("}\n\n")

def main():
    base_dir = "results"
    all_X = []
    all_y = []

    if not os.path.exists(base_dir):
        print("Results directory not found. Please run experiments first.")
        return

    design_count = 0
    print("Loading data from generated CSVs and assigning Good/Average/Poor labels...")
    for design in os.listdir(base_dir):
        design_dir = os.path.join(base_dir, design)
        feat_path = os.path.join(design_dir, "cuts_all_features.csv")
        surv_path = os.path.join(design_dir, "cuts_survivors.csv")

        if not os.path.exists(feat_path) or not os.path.exists(surv_path):
            continue
            
        try:
            feat_df = pd.read_csv(feat_path)
            surv_df = pd.read_csv(surv_path)
            
            merged = pd.merge(feat_df, surv_df, on=['node_id', 'cut_id'])
            
            # Synthesize 3 classes based on heuristic survival
            # We use survives_dominance (baseline mapper) and survives_volume (leaves <= 4)
            s_dom = merged['survives_dominance'].astype(int).values
            s_vol = merged['survives_volume'].astype(int).values
            
            # score = 0 (Poor) -> survives neither
            # score = 1 (Average) -> survives only one (mostly dominance but too large)
            # score = 2 (Good) -> survives both (structural, small, and dominant)
            score = s_dom + s_vol
            
            cols = ['nLeaves', 'nVolume', 'max_level', 'avg_level', 'random_val', 'uTruth', 'uTruth_popcount', 'max_leaf_refs', 'max_arrival']
            X = merged[cols].astype(float).values
            y = score

            all_X.append(X)
            all_y.append(y)
            design_count += 1
        except Exception as e:
            print(f"Skipping {design} due to error: {e}")

    if not all_X:
        print("No valid data loaded. Exiting.")
        return

    X = np.vstack(all_X)
    y = np.concatenate(all_y)

    print(f"Successfully loaded {len(X)} cuts from {design_count} designs.")
    
    # Class distribution
    unique, counts = np.unique(y, return_counts=True)
    dist = dict(zip(unique, counts))
    print(f"Class Distribution:")
    print(f" - Class 0 (Poor): {dist.get(0, 0)}")
    print(f" - Class 1 (Average): {dist.get(1, 0)}")
    print(f" - Class 2 (Good): {dist.get(2, 0)}")

    print("\nTraining small Random Forest Multi-Class Classifier (with Balanced Weights)...")
    clf = RandomForestClassifier(n_estimators=15, max_depth=8, class_weight='balanced', random_state=42)
    clf.fit(X, y)

    preds = clf.predict(X)
    print("\nClassification Report (0=Poor, 1=Average, 2=Good):")
    print(classification_report(y, preds))
    
    # Feature importance
    print("\nFeature Importances:")
    feat_names = ['nLeaves', 'nVolume', 'max_level', 'avg_level', 'random_val', 'uTruth', 'uTruth_popcount', 'max_leaf_refs', 'max_arrival']
    for name, imp in zip(feat_names, clf.feature_importances_):
        print(f" - {name}: {imp:.4f}")

    print("\nWriting multi-class inference model to native C header (ml_inference.h)...")
    with open("ml_inference.h", "w") as f:
        f.write("#ifndef ML_INFERENCE_H\n")
        f.write("#define ML_INFERENCE_H\n\n")
        
        n_classes = len(clf.classes_)
        
        # Write individual trees
        for i, estimator in enumerate(clf.estimators_):
            tree_to_c(estimator, feat_names, i, f, n_classes=n_classes)
            
        # Write ensemble function
        f.write(f"static int ML_Predict_Cut(float f0, float f1, float f2, float f3, float f4, float f5, float f6, float f7, float f8) {{\n")
        f.write("  float features[9] = {f0, f1, f2, f3, f4, f5, f6, f7, f8};\n")
        f.write(f"  float out_probs[{n_classes}] = {{0.0f}};\n")
        
        for i in range(len(clf.estimators_)):
            f.write(f"  tree_{i}_predict(features, out_probs);\n")
            
        f.write("  \n  // Find argmax class\n")
        f.write("  int best_class = 0;\n")
        f.write("  float max_prob = out_probs[0];\n")
        f.write(f"  for (int i = 1; i < {n_classes}; i++) {{\n")
        f.write("    if (out_probs[i] > max_prob) {\n")
        f.write("      max_prob = out_probs[i];\n")
        f.write("      best_class = i;\n")
        f.write("    }\n")
        f.write("  }\n")
        f.write("  return best_class; // 0=Poor, 1=Average, 2=Good\n")
        f.write("}\n\n")
        f.write("#endif // ML_INFERENCE_H\n")

    print("\nDone! Compiled C header `ml_inference.h` generated.")

if __name__ == "__main__":
    main()

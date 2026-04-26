#include "ml_cut.h"
#include "mapperInt.h"
#include "ml_inference.h"

#define ML_BASELINE_CUT_LIMIT 250

static int ML_PopCount32(unsigned x) {
  int c = 0;
  while (x) {
    x &= (x - 1);
    c++;
  }
  return c;
}

static void ML_PredictCutProbs(float f0, float f1, float f2, float f3, float f4,
                               float f5, float f6, float f7, float f8,
                               float out_probs[3]) {
  float features[9];
  int i;

  features[0] = f0;
  features[1] = f1;
  features[2] = f2;
  features[3] = f3;
  features[4] = f4;
  features[5] = f5;
  features[6] = f6;
  features[7] = f7;
  features[8] = f8;
  out_probs[0] = 0.0f;
  out_probs[1] = 0.0f;
  out_probs[2] = 0.0f;

  tree_0_predict(features, out_probs);
  tree_1_predict(features, out_probs);
  tree_2_predict(features, out_probs);
  tree_3_predict(features, out_probs);
  tree_4_predict(features, out_probs);
  tree_5_predict(features, out_probs);
  tree_6_predict(features, out_probs);
  tree_7_predict(features, out_probs);
  tree_8_predict(features, out_probs);
  tree_9_predict(features, out_probs);
  tree_10_predict(features, out_probs);
  tree_11_predict(features, out_probs);
  tree_12_predict(features, out_probs);
  tree_13_predict(features, out_probs);
  tree_14_predict(features, out_probs);

  for (i = 0; i < 3; i++)
    out_probs[i] /= 15.0f;
}

static void ML_ExtractCutFeatures(Map_Cut_t *pCut, Map_Node_t *pNode,
                                  float *pLeaves, float *pVolume,
                                  float *pNodeLevel, float *pAvgLeafLevel,
                                  float *pTruthOnes, float *pTruthXorEdges,
                                  float *pHasPhase0Match,
                                  float *pHasPhase1Match, float *pPlaceholder) {
  int i;
  int avgLeafLevel;
  int leaves;
  int truthOnes;
  int truthXorEdges;
  int truthValid;

  leaves = (int)pCut->nLeaves;
  *pLeaves = (float)leaves;
  *pVolume = (float)((int)pCut->nVolume);
  *pNodeLevel = (float)((int)pNode->Level);

  avgLeafLevel = 0;
  for (i = 0; i < leaves; i++)
    avgLeafLevel += (int)pCut->ppLeaves[i]->Level;
  if (leaves > 0)
    avgLeafLevel /= leaves;
  *pAvgLeafLevel = (float)avgLeafLevel;

  /*
   * The embedded model was trained from a dataset where truth-derived
   * features were effectively absent. Keep these features conservative
   * unless the cut truth looks genuinely initialized for a non-trivial cut.
   */
  truthValid =
      (pCut->nLeaves >= 4 && pCut->uTruth != 0 && pCut->uTruth != 0xAAAAAAAA);
  truthOnes = truthValid ? ML_PopCount32(pCut->uTruth) : 0;
  truthXorEdges =
      truthValid ? ML_PopCount32(pCut->uTruth ^ (pCut->uTruth >> 1)) : 0;
  *pTruthOnes = (float)truthOnes;
  *pTruthXorEdges = (float)truthXorEdges;

  *pHasPhase0Match = (float)(pCut->M[0].pSupers != NULL);
  *pHasPhase1Match = (float)(pCut->M[1].pSupers != NULL);
  *pPlaceholder = 0.0f;
}

float ML_ScoreCut(Map_Cut_t *pCut, Map_Node_t *pNode) {
  float leaves, volume, nodeLevel, avgLeafLevel;
  float truthOnes, truthXorEdges;
  float hasPhase0Match, hasPhase1Match, placeholder;
  float probs[3];
  float mlScore, heuristicScore;

  ML_ExtractCutFeatures(pCut, pNode, &leaves, &volume, &nodeLevel,
                        &avgLeafLevel, &truthOnes, &truthXorEdges,
                        &hasPhase0Match, &hasPhase1Match, &placeholder);

  ML_PredictCutProbs(leaves, volume, nodeLevel, avgLeafLevel, truthOnes,
                     truthXorEdges, hasPhase0Match, hasPhase1Match, placeholder,
                     probs);

  /*
   * The trained model is binary in practice (labels 0/1), while the
   * generated header still exposes three output slots. Use the margin
   * between the observed positive/negative classes as a weak prior and
   * blend it with a structural heuristic that remains valid even when the
   * training/export pipeline is imperfect.
   */
  mlScore = (probs[1] - probs[0]) + 0.25f * probs[2];

  heuristicScore = 0.60f * leaves;
  heuristicScore += 0.18f * volume;
  heuristicScore += 0.08f * (nodeLevel - avgLeafLevel);
  heuristicScore -= 0.45f * hasPhase0Match;
  heuristicScore -= 0.45f * hasPhase1Match;
  heuristicScore -= 0.02f * truthOnes;
  heuristicScore -= 0.01f * truthXorEdges;

  return (2.0f * mlScore) - heuristicScore;
}

int ML_ClassifyCut(Map_Cut_t *pCut, Map_Node_t *pNode) {
  float score;

  if (g_mode == 0)
    return 0;

  score = ML_ScoreCut(pCut, pNode);

  if (score >= 0.20f)
    return 0;
  if (score >= -0.35f)
    return 1;
  return 2;
}

int ML_CutLimitForMode(int mode) {
  if (mode <= 0)
    return ML_BASELINE_CUT_LIMIT;
  if (mode == 1)
    return 20;
  if (mode == 2)
    return 14;
  return 10;
}

int ML_CutPrefilterLimitForMode(int mode) {
  if (mode <= 0)
    return ML_BASELINE_CUT_LIMIT;
  if (mode == 1)
    return 96;
  if (mode == 2)
    return 64;
  return 40;
}

int ML_CutMinKeepForMode(int mode) {
  if (mode <= 0)
    return ML_BASELINE_CUT_LIMIT;
  if (mode == 1)
    return 8;
  if (mode == 2)
    return 6;
  return 4;
}

float ML_CutScoreWindowForMode(int mode) {
  if (mode <= 0)
    return 0.0f;
  if (mode == 1)
    return 0.35f;
  if (mode == 2)
    return 0.25f;
  return 0.20f;
}

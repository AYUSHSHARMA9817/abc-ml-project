#ifndef ML_CUT_H
#define ML_CUT_H
#include "mapperInt.h"

int ML_ClassifyCut( Map_Cut_t * pCut, Map_Node_t * pNode );
float ML_ScoreCut( Map_Cut_t * pCut, Map_Node_t * pNode );
int ML_CutLimitForMode( int mode );
int ML_CutPrefilterLimitForMode( int mode );
int ML_CutMinKeepForMode( int mode );
float ML_CutScoreWindowForMode( int mode );

#endif

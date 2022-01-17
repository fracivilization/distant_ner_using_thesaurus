#!/bin/bash
dir=`dirname $0`
source ${dir}/params.sh

TMPFILE=$(mktemp)

echo "Chunker Match"
WITH_NC=True make train_pseudo_anno -j$(nproc) 2>&1

get_make_cmd () {
    CMD="TRAIN_SNT_NUM=${TRAIN_SNT_NUM} O_SAMPLING_RATIO=${O_SAMPLING_RATIO} POSITIVE_RATIO_THR_OF_NEGATIVE_CAT=${POSITIVE_RATIO_THR_OF_NEGATIVE_CAT} NEGATIVE_CATS=\"${NEGATIVE_CATS}\" WITH_O=${WITH_O} CHUNKER=${CHUNKER} make"
    echo ${CMD}
}

TRAIN_SNT_NUM=9223372036854775807
echo "GOLD"
# Get Dataset
# All Negatives
NEGATIVE_CATS=""
WITH_O=True
CHUNKER="enumerated"
POSITIVE_RATIO_THR_OF_NEGATIVE_CAT=1.0
O_SAMPLING_RATIO=1.0
MAKE=`get_make_cmd`
eval ${MAKE} train_on_gold 2>&1

echo "Span Classif. w/N.U."
# Get Dataset
# All Negatives
NEGATIVE_CATS=""
WITH_O=True
CHUNKER="enumerated"
POSITIVE_RATIO_THR_OF_NEGATIVE_CAT=1.0
# O_SAMPLING_RATIO=0.0001
O_SAMPLING_RATIO=0.03
MAKE=`get_make_cmd`
eval ${MAKE} train -j$(nproc)


echo "Span Classif. w/N.U. +Thesaurus Negatives"
NEGATIVE_CATS="T054 T055 T056 T064 T065 T066 T068 T075 T079 T080 T081 T099 T100 T101 T102 T171 T194 T200"
WITH_O=True
CHUNKER="enumerated"
POSITIVE_RATIO_THR_OF_NEGATIVE_CAT=1.0
O_SAMPLING_RATIO=0.03
O_SAMPLING_RATIO=0.005
MAKE=`get_make_cmd`
eval ${MAKE} train -j$(nproc) 
RUN_ID_Thesaurus_Negatives_UMLS=$(cat ${TMPFILE} | grep "mlflow_run_id" | awk '{print $2}')
echo "RUN_ID_Thesaurus_Negatives (UMLS)" ${RUN_ID_Thesaurus_Negatives_UMLS}
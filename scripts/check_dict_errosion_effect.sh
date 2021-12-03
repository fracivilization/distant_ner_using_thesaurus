TMPFILE=$(mktemp)

get_cmd () {
    CMD="\
        poetry run python -m cli.train \
        ++dataset.name_or_path=${RUN_DATASET} \
        ner_model/chunker=${CHUNKER} \
        ner_model.typer.msc_args.with_o=${WITH_O} \
        ner_model.typer.model_args.o_sampling_ratio=${O_SAMPLING_RATIO} \
        ner_model.typer.train_args.per_device_train_batch_size=8 \
        ner_model.typer.train_args.per_device_eval_batch_size=32 \
        ner_model.typer.train_args.do_train=True \
        ner_model.typer.train_args.overwrite_output_dir=True \
    "
    echo ${CMD}
}

check_erosion_effect () {
    RUN_DATASET=$(WITH_NC=${WITH_NC} make -n all | grep PSEUDO_DATA_ON_GOLD | awk '{print $3}')
    CMD=`get_cmd`
    echo ${CMD}
    eval ${CMD} 2>&1 | tee ${TMPFILE}
    RUN_ID_BASE=$(cat ${TMPFILE} | grep "mlflow_run_id" | awk '{print $2}')
    echo "RUN_ID_BASE" ${RUN_ID_BASE}

    RUN_DATASET=$(WITH_NC=${WITH_NC} make -n all | grep EROSION_PSEUDO_DATA | awk '{print $3}')
    CMD=`get_cmd`
    echo ${CMD}
    eval ${CMD} 2>&1 | tee ${TMPFILE}
    RUN_ID_WO_DICT_EROSION=$(cat ${TMPFILE} | grep "mlflow_run_id" | awk '{print $2}')
    echo "RUN_ID_WO_DICT_EROSION" ${RUN_ID_WO_DICT_EROSION}

    poetry run python -m cli.compare_metrics --base-run-id ${RUN_ID_BASE} --focus-run-id ${RUN_ID_WO_DICT_EROSION}
}


echo "All Negatives"
NEGATIVE_CATS=""
O_SAMPLING_RATIO=0.0001
WITH_O=True
CHUNKER="enumerated"
check_erosion_effect

echo "All Negatives (NP)"
NEGATIVE_CATS=""
O_SAMPLING_RATIO=0.02
WITH_O=True
CHUNKER="spacy_np"
check_erosion_effect

echo "Thesaurus Negatives (UMLS)"
NEGATIVE_CATS="T002 T004 T054 T055 T056 T064 T065 T066 T068 T075 T079 T080 T081 T099 T100 T101 T102 T171 T194 T200"
WITH_O=False
O_SAMPLING_RATIO=0.0 # This variable isn't needed but, I added for get_cmd function
CHUNKER="spacy_np"
check_erosion_effect
# Thesaurus Negatives (UMLS + DBPedia)
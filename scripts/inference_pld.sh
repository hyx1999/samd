#!/bin/bash
set -e
set -x

cd $(dirname $0)/..

devices=0

# vicuna-7b-v1.3
CUDA_VISIBLE_DEVICES=${devices} \
    python -m evaluation.inference_pld \
    --model-type vicuna \
    --bench-name spec_bench \
    --model-path /data/models/vicuna-7b-v1.3 \
    --model-id vicuna-7b-v1.3-pld

import time
import pickle
from datasets import Dataset
from transformers import PreTrainedTokenizerFast
from typing import List

from .sam import SAM
from ..samd_config import SamdConfig

def build_sam(
    config: SamdConfig,
    batch_tokens: List[List[int]],
    eos_token: int,
):
    sam = SAM.build(
        batch_tokens, 
        eos_token, 
        config.n_gram,
        config.k,
    )
    return sam

def dump_sam(path: str, sam: SAM):
    with open(path, "wb") as f:
        pickle.dump(sam, f)

def load_sam(path: str):
    print("load sam...")
    start = time.perf_counter()
    with open(path, "rb") as f:
        sam: SAM = pickle.load(f)
    end = time.perf_counter()
    assert type(sam) is SAM
    print("loading ended in {} seconds.".format(end - start))
    return sam

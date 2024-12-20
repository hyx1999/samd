import torch
from typing import List, Tuple, Dict
from dataclasses import dataclass
from copy import deepcopy
from collections import deque
from tqdm import tqdm

class SAM:
   
    @dataclass
    class SAMState:
        next: dict[int, int]
        link: int
        length: int
        min_endpos: int

    def __init__(self, n_predicts: int = 40):
        self.max_predicts = n_predicts
        self.states: List[SAM.SAMState] = [SAM.SAMState(next={}, link=-1, length=0, min_endpos=0)]
        self.input_ids: List[int] = [-1]
        self.last = 0
        self.max_length = 0
        
        # params needed to be reset for each query
        self.cur_index = 0
        self.cur_length = 0
    
    def reset(self):
        raise NotImplementedError
    
    def expand_state(self, state: SAMState):
        new_index = len(self.states)
        self.states.append(state)
        return new_index

    def add_state(self, token: int):
        self.max_length += 1
        cur = self.expand_state(
            SAM.SAMState(
                next={}, link=-1, 
                length=self.max_length, 
                min_endpos=self.max_length
            )
        )
        p = self.last
        while p != -1 and token not in self.states[p].next:
            self.states[p].next[token] = cur
            p = self.states[p].link
        if p == -1:
            self.states[cur].link = 0
        else:
            q = self.states[p].next[token]
            if self.states[p].length + 1 == self.states[q].length:
                self.states[cur].link = q
            else:
                clone = self.expand_state(deepcopy(self.states[q]))
                self.states[clone].length = self.states[p].length + 1
                while p != -1 and self.states[p].next[token] == q:
                    self.states[p].next[token] = clone
                    p = self.states[p].link
                self.states[q].link = self.states[cur].link = clone
        self.last = cur
           
    def transfer_state(self, index: int, length: int, token: int):
        while index != 0 and token not in self.states[index].next:
            index = self.states[index].link
            length = self.states[index].length
        if token in self.states[index].next:
            index = self.states[index].next[token]
            length += 1
        else:
            index = length = 0
        return index, length
    
    def transfer_cur_state(self, token: int):
        self.cur_index, self.cur_length = \
            self.transfer_state(self.cur_index, self.cur_length, token)
    
    def to_anc(self, index: int, length: int):
        length_to_end = self.max_length - self.states[index].min_endpos
        while index != 0 and self.max_predicts > length_to_end:
            index = self.states[index].link
            length = self.states[index].length
            length_to_end = self.max_length - self.states[index].min_endpos
        return index, length
    
    def add_tokens(self, tokens: List[int]):
        for token in tokens:
            self.add_state(token)
            self.transfer_cur_state(token)
        self.input_ids.extend(tokens)
        self.cur_index, self.cur_length = \
            self.to_anc(self.cur_index, self.cur_length)
    
    def transfer_tokens(self, tokens: List[int]):
        for token in tokens:
            self.transfer_cur_state(token)
        self.cur_index, self.cur_length = \
            self.to_anc(self.cur_index, self.cur_length)

    def lookup(self, token: int):
        index, length = \
            self.transfer_state(self.cur_index, self.cur_length, token)
        index, length = \
            self.to_anc(index, length)
        endpos = self.states[index].min_endpos
        pred_ids = self.input_ids[endpos + 1:endpos + self.max_predicts + 1]
        if len(pred_ids) < self.max_predicts:
            pred_ids.extend([0] * (self.max_predicts - len(pred_ids)))
        return pred_ids, length


class DynSAM(SAM):
        
    def reset(self):
        self.states: List[SAM.SAMState] = [SAM.SAMState(next={}, link=-1, length=0, min_endpos=0)]
        self.input_ids: List[int] = [-1]
        self.last = 0
        self.max_length = 0
        self.cur_index = 0
        self.cur_length = 0


class StaticSAM(SAM):

    def reset(self):
        self.cur_index = 0
        self.cur_length = 0

    def add_batch_tokens(self, batch_tokens: List[List[int]], eos_token: int, verbose: bool):
        for tokens in tqdm(batch_tokens, desc="build sam...", disable=not verbose):
            self.add_tokens(tokens)
            if tokens[-1] != eos_token:
                self.add_tokens([eos_token])

    @staticmethod
    def build(
        batch_tokens: List[List[int]], 
        eos_token: int,
        n_predict: int,
        verbose: bool =True
    ):
        sam = StaticSAM(n_predict)
        sam.add_batch_tokens(batch_tokens, eos_token, verbose)
        return sam

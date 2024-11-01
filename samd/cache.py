import numpy as np
import torch
from transformers.cache_utils import Cache, StaticCache
from transformers.configuration_utils import PretrainedConfig
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum


class SamdCache(Cache):
    
    def __init__(self, config: PretrainedConfig, max_batch_size: int, max_cache_len: int, device, dtype=None) -> None:
        super().__init__()
        self.config = config
        self.max_batch_size = max_batch_size
        self.max_cache_len = max_cache_len
        self.cur_length = torch.tensor(0, dtype=torch.long, device=device)
        self.kv_data = torch.zeros(
            config.num_hidden_layers * 2,
            max_batch_size,
            config.num_key_value_heads,
            max_cache_len,
            config.hidden_size // config.num_attention_heads,
            device=device,
            dtype=dtype
        )
        self.devcie = device
        self.dtype = dtype
    
    def get_seq_length(self, layer_idx: int | None = 0) -> int:
        return self.cur_length.item()
    
    def get_max_cache_shape(self) -> int:
        return self.max_cache_len
    
    def reorder_cache(self, beam_idx):
        raise NotImplementedError
    
    def reset(self):
        self.kv_data.fill_(0)
        self.cur_length.fill_(0)
    
    def update(
        self,
        key_states: torch.Tensor,
        value_states: torch.Tensor,
        layer_idx: int,
        cache_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        start = self.cur_length
        length = key_states.shape[-2]        
        self.kv_data[2 * layer_idx + 0]\
            .narrow(-2, start, length)\
            .copy_(key_states)
        self.kv_data[2 * layer_idx + 1]\
            .narrow(-2, start, length)\
            .copy_(value_states)

        k_out = self.kv_data[2 * layer_idx + 0].narrow(-2, 0, start + length)
        v_out = self.kv_data[2 * layer_idx + 1].narrow(-2, 0, start + length)
        return k_out, v_out
    
    def post_update(self, indices: torch.Tensor):
        start = self.cur_length
        select_indices = start + indices
        accept_length = indices.shape[-1]
        tgt = self.kv_data.index_select(-2, select_indices)
        dst = self.kv_data.narrow(-2, start, accept_length)
        dst.copy_(tgt)
        self.cur_length += accept_length

    def set_cache_positions(self, length):
        self.cur_length.fill_(length)


class SamdStaticCache(StaticCache):
    
    def __init__(self, config: PretrainedConfig, max_batch_size: int, max_cache_len: int, device, dtype=None) -> None:
        super().__init__(config, max_batch_size, max_cache_len, device, dtype)
        self.cur_length = torch.tensor(0, dtype=torch.long, device=device)
        self.devcie = device
    
    def get_seq_length(self, layer_idx: int | None = 0) -> int:
        return self.cur_length.item()
    
    def reset(self):
        super().reset()
        self.cur_length.fill_(0)
    
    def update(
        self,
        key_states: torch.Tensor,
        value_states: torch.Tensor,
        layer_idx: int,
        cache_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        start = self.cur_length
        self.key_cache[layer_idx] = self.key_cache[layer_idx].to(device=key_states.device)
        self.value_cache[layer_idx] = self.value_cache[layer_idx].to(device=value_states.device)
        k_out = self.key_cache[layer_idx]
        v_out = self.value_cache[layer_idx]

        key_length = value_length = key_states.shape[2]
        k_out[:, :, start:start + key_length] = key_states
        v_out[:, :, start:start + value_length] = value_states

        return k_out, v_out
    
    @torch.no_grad()
    def post_update(self, indices: torch.Tensor):
        start = self.cur_length
        select_positions = self.cur_length + indices
        accept_length = indices.shape[-1]
        for layer_idx in range(len(self.key_cache)):
            self.key_cache[layer_idx][:, :, start:start + accept_length] \
                = self.key_cache[layer_idx][:, :, select_positions]
            self.value_cache[layer_idx][:, :, start:start + accept_length] \
                = self.value_cache[layer_idx][:, :, select_positions]
        self.cur_length += accept_length

    @torch.no_grad()
    def set_cache_positions(self, length):
        self.cur_length.fill_(length)

"""PatchTST runtime model (strict-load compatible with Time-Series-Library checkpoints)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn

from inference_engine.dc_runtime_layers import AttentionLayer, Encoder, EncoderLayer, FullAttention


class Transpose(nn.Module):
    def __init__(self, *dims: int, contiguous: bool = False) -> None:
        super().__init__()
        self.dims = dims
        self.contiguous = contiguous

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.transpose(*self.dims)
        if self.contiguous:
            return x.contiguous()
        return x


class PositionalEmbedding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 5000) -> None:
        super().__init__()
        pe = torch.zeros(max_len, d_model).float()
        position = torch.arange(0, max_len).float().unsqueeze(1)
        div_term = (
            torch.arange(0, d_model, 2).float() * -(torch.log(torch.tensor(10000.0)) / d_model)
        ).exp()
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.pe[:, : x.size(1)]


class PatchEmbedding(nn.Module):
    def __init__(
        self,
        d_model: int,
        patch_len: int,
        stride: int,
        padding: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.patch_len = patch_len
        self.stride = stride
        self.padding_patch_layer = nn.ReplicationPad1d((0, padding))
        self.value_embedding = nn.Linear(patch_len, d_model, bias=False)
        self.position_embedding = PositionalEmbedding(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, int]:
        n_vars = x.shape[1]
        x = self.padding_patch_layer(x)
        x = x.unfold(dimension=-1, size=self.patch_len, step=self.stride)
        x = torch.reshape(x, (x.shape[0] * x.shape[1], x.shape[2], x.shape[3]))
        x = self.value_embedding(x) + self.position_embedding(x)
        return self.dropout(x), n_vars


class FlattenHead(nn.Module):
    def __init__(self, n_vars: int, nf: int, target_window: int, head_dropout: float = 0.0) -> None:
        super().__init__()
        self.n_vars = n_vars
        self.flatten = nn.Flatten(start_dim=-2)
        self.linear = nn.Linear(nf, target_window)
        self.dropout = nn.Dropout(head_dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.flatten(x)
        x = self.linear(x)
        return self.dropout(x)


@dataclass(frozen=True)
class PatchTSTConfig:
    task_name: str = "long_term_forecast"
    seq_len: int = 512
    label_len: int = 48
    pred_len: int = 24
    enc_in: int = 1
    d_model: int = 128
    n_heads: int = 16
    e_layers: int = 3
    d_ff: int = 512
    factor: int = 1
    dropout: float = 0.1
    activation: str = "gelu"
    patch_len: int = 16
    stride: int = 8


class PatchTSTRuntimeModel(nn.Module):
    """Minimal PatchTST forecasting runtime with checkpoint-compatible keys."""

    def __init__(self, configs: PatchTSTConfig) -> None:
        super().__init__()
        if configs.task_name not in {"long_term_forecast", "short_term_forecast"}:
            raise ValueError("PatchTST only supports forecasting tasks.")

        self.task_name = configs.task_name
        self.seq_len = configs.seq_len
        self.label_len = configs.label_len
        self.pred_len = configs.pred_len
        padding = configs.stride

        self.patch_embedding = PatchEmbedding(
            configs.d_model,
            configs.patch_len,
            configs.stride,
            padding,
            configs.dropout,
        )
        self.encoder = Encoder(
            [
                EncoderLayer(
                    AttentionLayer(
                        FullAttention(
                            False,
                            configs.factor,
                            attention_dropout=configs.dropout,
                            output_attention=False,
                        ),
                        configs.d_model,
                        configs.n_heads,
                    ),
                    configs.d_model,
                    configs.d_ff,
                    dropout=configs.dropout,
                    activation=configs.activation,
                )
                for _ in range(configs.e_layers)
            ],
            norm_layer=nn.Sequential(
                Transpose(1, 2),
                nn.BatchNorm1d(configs.d_model),
                Transpose(1, 2),
            ),
        )
        head_nf = configs.d_model * int((configs.seq_len - configs.patch_len) / configs.stride + 2)
        self.head = FlattenHead(configs.enc_in, head_nf, configs.pred_len, head_dropout=configs.dropout)

    def forecast(self, x_enc, x_mark_enc, x_dec, x_mark_dec):
        del x_mark_enc, x_dec, x_mark_dec

        means = x_enc.mean(1, keepdim=True).detach()
        x_enc = x_enc - means
        stdev = torch.sqrt(torch.var(x_enc, dim=1, keepdim=True, unbiased=False) + 1e-5)
        x_enc = x_enc / stdev

        x_enc = x_enc.permute(0, 2, 1)
        enc_out, n_vars = self.patch_embedding(x_enc)
        enc_out, _attns = self.encoder(enc_out)
        enc_out = torch.reshape(enc_out, (-1, n_vars, enc_out.shape[-2], enc_out.shape[-1]))
        enc_out = enc_out.permute(0, 1, 3, 2)

        dec_out = self.head(enc_out)
        dec_out = dec_out.permute(0, 2, 1)
        dec_out = dec_out * (stdev[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1))
        dec_out = dec_out + (means[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1))
        return dec_out

    def forward(self, x_enc, x_mark_enc, x_dec, x_mark_dec, mask=None):
        del mask
        dec_out = self.forecast(x_enc, x_mark_enc, x_dec, x_mark_dec)
        return dec_out[:, -self.pred_len :, :]


def _infer_e_layers(state_dict: dict[str, torch.Tensor]) -> int:
    layers: set[int] = set()
    for key in state_dict:
        match = re.match(r"encoder\.attn_layers\.(\d+)\.", key)
        if match:
            layers.add(int(match.group(1)))
    return max(layers) + 1 if layers else 3


def build_patchtst_for_state_dict(
    state_dict: dict[str, torch.Tensor],
) -> tuple[PatchTSTRuntimeModel, PatchTSTConfig]:
    patch_weight = state_dict["patch_embedding.value_embedding.weight"]
    d_model = int(patch_weight.shape[0])
    patch_len = int(patch_weight.shape[1])
    pred_len = int(state_dict["head.linear.weight"].shape[0])
    head_nf = int(state_dict["head.linear.weight"].shape[1])
    d_ff = int(state_dict["encoder.attn_layers.0.conv1.weight"].shape[0])
    e_layers = _infer_e_layers(state_dict)
    stride = 8
    patch_num = head_nf // d_model
    seq_len = (patch_num - 2) * stride + patch_len

    cfg = PatchTSTConfig(
        seq_len=seq_len,
        pred_len=pred_len,
        d_model=d_model,
        e_layers=e_layers,
        d_ff=d_ff,
        patch_len=patch_len,
        stride=stride,
    )
    model = PatchTSTRuntimeModel(cfg)
    return model, cfg


def load_patchtst_checkpoint(
    path: Path,
    *,
    map_location: str | torch.device = "cpu",
) -> tuple[PatchTSTRuntimeModel, PatchTSTConfig]:
    raw = torch.load(path, map_location=map_location)
    if not isinstance(raw, dict):
        raise TypeError("checkpoint 应为包含权重键的 dict / OrderedDict。")
    state_dict = raw
    model, cfg = build_patchtst_for_state_dict(state_dict)
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model, cfg

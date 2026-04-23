"""Minimal TimeXer runtime model (strict-load compatible with Time-Series-Library checkpoints)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from inference_engine.dc_runtime_layers import AttentionLayer, FullAttention


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


class DataEmbeddingInverted(nn.Module):
    def __init__(
        self,
        c_in: int,
        d_model: int,
        _embed_type: str = "timeF",
        _freq: str = "h",
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.value_embedding = nn.Linear(c_in, d_model)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x: torch.Tensor, x_mark: torch.Tensor | None) -> torch.Tensor:
        x = x.permute(0, 2, 1)
        if x_mark is None:
            x = self.value_embedding(x)
        else:
            x = self.value_embedding(torch.cat([x, x_mark.permute(0, 2, 1)], dim=1))
        return self.dropout(x)


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


class EnEmbedding(nn.Module):
    def __init__(self, n_vars: int, d_model: int, patch_len: int, dropout: float) -> None:
        super().__init__()
        self.patch_len = patch_len
        self.value_embedding = nn.Linear(patch_len, d_model, bias=False)
        self.glb_token = nn.Parameter(torch.randn(1, n_vars, 1, d_model))
        self.position_embedding = PositionalEmbedding(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, int]:
        n_vars = x.shape[1]
        glb = self.glb_token.repeat((x.shape[0], 1, 1, 1))

        x = x.unfold(dimension=-1, size=self.patch_len, step=self.patch_len)
        x = torch.reshape(x, (x.shape[0] * x.shape[1], x.shape[2], x.shape[3]))
        x = self.value_embedding(x) + self.position_embedding(x)
        x = torch.reshape(x, (-1, n_vars, x.shape[-2], x.shape[-1]))
        x = torch.cat([x, glb], dim=2)
        x = torch.reshape(x, (x.shape[0] * x.shape[1], x.shape[2], x.shape[3]))
        return self.dropout(x), n_vars


class EncoderLayer(nn.Module):
    def __init__(
        self,
        self_attention: AttentionLayer,
        cross_attention: AttentionLayer,
        d_model: int,
        d_ff: int | None = None,
        dropout: float = 0.1,
        activation: str = "gelu",
    ) -> None:
        super().__init__()
        d_ff = d_ff or 4 * d_model
        self.self_attention = self_attention
        self.cross_attention = cross_attention
        self.conv1 = nn.Conv1d(in_channels=d_model, out_channels=d_ff, kernel_size=1)
        self.conv2 = nn.Conv1d(in_channels=d_ff, out_channels=d_model, kernel_size=1)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        self.activation = F.relu if activation == "relu" else F.gelu

    def forward(
        self,
        x: torch.Tensor,
        cross: torch.Tensor,
        x_mask=None,
        cross_mask=None,
        tau=None,
        delta=None,
    ) -> torch.Tensor:
        batch, _length, d_model = cross.shape
        x = x + self.dropout(
            self.self_attention(x, x, x, attn_mask=x_mask, tau=tau, delta=None)[0]
        )
        x = self.norm1(x)

        x_glb_ori = x[:, -1, :].unsqueeze(1)
        x_glb = torch.reshape(x_glb_ori, (batch, -1, d_model))
        x_glb_attn = self.dropout(
            self.cross_attention(
                x_glb,
                cross,
                cross,
                attn_mask=cross_mask,
                tau=tau,
                delta=delta,
            )[0]
        )
        x_glb_attn = torch.reshape(
            x_glb_attn, (x_glb_attn.shape[0] * x_glb_attn.shape[1], x_glb_attn.shape[2])
        ).unsqueeze(1)
        x_glb = x_glb_ori + x_glb_attn
        x_glb = self.norm2(x_glb)

        y = x = torch.cat([x[:, :-1, :], x_glb], dim=1)
        y = self.dropout(self.activation(self.conv1(y.transpose(-1, 1))))
        y = self.dropout(self.conv2(y).transpose(-1, 1))
        return self.norm3(x + y)


class Encoder(nn.Module):
    def __init__(self, layers: list[EncoderLayer], norm_layer: nn.Module | None = None) -> None:
        super().__init__()
        self.layers = nn.ModuleList(layers)
        self.norm = norm_layer

    def forward(
        self,
        x: torch.Tensor,
        cross: torch.Tensor,
        x_mask=None,
        cross_mask=None,
        tau=None,
        delta=None,
    ) -> torch.Tensor:
        for layer in self.layers:
            x = layer(x, cross, x_mask=x_mask, cross_mask=cross_mask, tau=tau, delta=delta)
        if self.norm is not None:
            x = self.norm(x)
        return x


@dataclass(frozen=True)
class TimeXerConfig:
    task_name: str = "long_term_forecast"
    features: str = "S"
    seq_len: int = 512
    label_len: int = 48
    pred_len: int = 24
    enc_in: int = 1
    d_model: int = 128
    n_heads: int = 16
    e_layers: int = 3
    d_ff: int = 512
    factor: int = 1
    embed: str = "timeF"
    freq: str = "h"
    dropout: float = 0.1
    activation: str = "gelu"
    patch_len: int = 16
    use_norm: bool = True


class TimeXerRuntimeModel(nn.Module):
    """Minimal single-variable TimeXer runtime for strict checkpoint loading."""

    def __init__(self, configs: TimeXerConfig) -> None:
        super().__init__()
        if configs.task_name not in {"long_term_forecast", "short_term_forecast"}:
            raise ValueError("TimeXer only supports forecasting tasks.")
        if configs.features != "S" or configs.enc_in != 1:
            raise ValueError("This runtime only supports the single-variable TimeXer route.")
        if configs.seq_len % configs.patch_len != 0:
            raise ValueError("TimeXer runtime requires seq_len to be divisible by patch_len.")

        self.task_name = configs.task_name
        self.features = configs.features
        self.seq_len = configs.seq_len
        self.label_len = configs.label_len
        self.pred_len = configs.pred_len
        self.use_norm = configs.use_norm
        self.patch_len = configs.patch_len
        self.patch_num = configs.seq_len // configs.patch_len
        self.n_vars = configs.enc_in

        self.en_embedding = EnEmbedding(self.n_vars, configs.d_model, self.patch_len, configs.dropout)
        self.ex_embedding = DataEmbeddingInverted(
            configs.seq_len, configs.d_model, configs.embed, configs.freq, configs.dropout
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
            norm_layer=nn.LayerNorm(configs.d_model),
        )
        head_nf = configs.d_model * (self.patch_num + 1)
        self.head = FlattenHead(configs.enc_in, head_nf, configs.pred_len, head_dropout=configs.dropout)

    def forecast(self, x_enc, x_mark_enc, x_dec, x_mark_dec):
        del x_dec, x_mark_dec

        if x_mark_enc is None:
            raise ValueError("TimeXer 单变量推理需要提供 x_mark_enc 时间特征。")

        if self.use_norm:
            means = x_enc.mean(1, keepdim=True).detach()
            x_enc = x_enc - means
            stdev = torch.sqrt(torch.var(x_enc, dim=1, keepdim=True, unbiased=False) + 1e-5)
            x_enc = x_enc / stdev
        else:
            means = None
            stdev = None

        _batch, _length, n = x_enc.shape
        if n != 1:
            raise ValueError(f"TimeXer runtime 仅支持单变量输入，当前 enc_in={n}。")

        en_embed, n_vars = self.en_embedding(
            x_enc[:, :, -1].unsqueeze(-1).permute(0, 2, 1)
        )
        ex_embed = self.ex_embedding(x_enc[:, :, :-1], x_mark_enc)

        enc_out = self.encoder(en_embed, ex_embed)
        enc_out = torch.reshape(enc_out, (-1, n_vars, enc_out.shape[-2], enc_out.shape[-1]))
        enc_out = enc_out.permute(0, 1, 3, 2)

        dec_out = self.head(enc_out)
        dec_out = dec_out.permute(0, 2, 1)

        if self.use_norm:
            assert means is not None and stdev is not None
            dec_out = dec_out * (stdev[:, 0, -1:].unsqueeze(1).repeat(1, self.pred_len, 1))
            dec_out = dec_out + (means[:, 0, -1:].unsqueeze(1).repeat(1, self.pred_len, 1))

        return dec_out

    def forward(self, x_enc, x_mark_enc, x_dec, x_mark_dec, mask=None):
        del mask
        dec_out = self.forecast(x_enc, x_mark_enc, x_dec, x_mark_dec)
        return dec_out[:, -self.pred_len :, :]


def _infer_e_layers(state_dict: dict[str, torch.Tensor]) -> int:
    layers: set[int] = set()
    for key in state_dict:
        match = re.match(r"encoder\.layers\.(\d+)\.", key)
        if match:
            layers.add(int(match.group(1)))
    return max(layers) + 1 if layers else 3


def build_timexer_for_state_dict(
    state_dict: dict[str, torch.Tensor],
) -> tuple[TimeXerRuntimeModel, TimeXerConfig]:
    d_model, patch_len = state_dict["en_embedding.value_embedding.weight"].shape
    pred_len = int(state_dict["head.linear.weight"].shape[0])
    head_nf = int(state_dict["head.linear.weight"].shape[1])
    seq_len = int(state_dict["ex_embedding.value_embedding.weight"].shape[1])
    d_ff = int(state_dict["encoder.layers.0.conv1.weight"].shape[0])
    e_layers = _infer_e_layers(state_dict)

    if head_nf % d_model != 0:
        raise ValueError(
            f"TimeXer checkpoint 头部维度异常：head_nf={head_nf} 不能被 d_model={d_model} 整除。"
        )
    patch_num_plus_glb = head_nf // d_model
    if patch_num_plus_glb < 2:
        raise ValueError(f"TimeXer checkpoint patch 数异常：{patch_num_plus_glb}。")

    cfg = TimeXerConfig(
        seq_len=seq_len,
        label_len=48,
        pred_len=pred_len,
        enc_in=1,
        d_model=int(d_model),
        n_heads=16,
        e_layers=e_layers,
        d_ff=d_ff,
        factor=1,
        dropout=0.1,
        activation="gelu",
        patch_len=int(patch_len),
        use_norm=True,
    )
    model = TimeXerRuntimeModel(cfg)
    return model, cfg


def load_timexer_checkpoint(
    path: Path,
    *,
    map_location: str | torch.device = "cpu",
) -> tuple[TimeXerRuntimeModel, TimeXerConfig]:
    raw = torch.load(path, map_location=map_location)
    if not isinstance(raw, dict):
        raise TypeError("checkpoint 应为包含权重键的 dict / OrderedDict。")
    state_dict = raw
    model, cfg = build_timexer_for_state_dict(state_dict)
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model, cfg

"""DC-iTransformer runtime (strict-load compatible with Time-Series-Library checkpoints)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import torch
import torch.nn as nn

from inference_engine.dc_runtime_layers import AttentionLayer, Encoder, EncoderLayer, FullAttention


@dataclass(frozen=True)
class DCITransformerConfig:
    task_name: str = "long_term_forecast"
    seq_len: int = 256
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


class DataEmbeddingInverted(nn.Module):
    """Inverted embedding (matches ``layers.Embed.DataEmbedding_inverted``)."""

    def __init__(self, c_in: int, d_model: int, _embed_type: str = "fixed", _freq: str = "h", dropout: float = 0.1):
        super().__init__()
        self.value_embedding = nn.Linear(c_in, d_model)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x, x_mark):
        x = x.permute(0, 2, 1)
        if x_mark is None:
            x = self.value_embedding(x)
        else:
            x = self.value_embedding(torch.cat([x, x_mark.permute(0, 2, 1)], 1))
        return self.dropout(x)


class DCITransformer(nn.Module):
    """Depthwise local CNN + iTransformer encoder head (``models.DC_iTransformer.Model``)."""

    def __init__(self, configs: DCITransformerConfig) -> None:
        super().__init__()
        if configs.task_name not in {"long_term_forecast", "short_term_forecast"}:
            raise ValueError("DC-iTransformer only supports forecasting tasks.")

        self.task_name = configs.task_name
        self.seq_len = configs.seq_len
        self.pred_len = configs.pred_len

        self.local_cnn = nn.Sequential(
            nn.Conv1d(
                in_channels=configs.enc_in,
                out_channels=configs.enc_in,
                kernel_size=3,
                padding=1,
                groups=configs.enc_in,
            ),
            nn.GELU(),
        )
        self.enc_embedding = DataEmbeddingInverted(
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
                    configs.d_model,
                    configs.d_ff,
                    dropout=configs.dropout,
                    activation=configs.activation,
                )
                for _ in range(configs.e_layers)
            ],
            norm_layer=torch.nn.LayerNorm(configs.d_model),
        )
        self.projection = nn.Linear(configs.d_model, configs.pred_len, bias=True)

    def forecast(self, x_enc, x_mark_enc, x_dec, x_mark_dec):
        del x_dec, x_mark_dec

        means = x_enc.mean(1, keepdim=True).detach()
        x_enc = x_enc - means
        stdev = torch.sqrt(torch.var(x_enc, dim=1, keepdim=True, unbiased=False) + 1e-5)
        x_enc /= stdev

        _b, _l, n = x_enc.shape

        x_enc = self.local_cnn(x_enc.permute(0, 2, 1)).permute(0, 2, 1)
        enc_out = self.enc_embedding(x_enc, x_mark_enc)
        enc_out, _attns = self.encoder(enc_out, attn_mask=None)

        dec_out = self.projection(enc_out).permute(0, 2, 1)[:, :, :n]
        dec_out = dec_out * (stdev[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1))
        dec_out = dec_out + (means[:, 0, :].unsqueeze(1).repeat(1, self.pred_len, 1))
        return dec_out

    def forward(self, x_enc, x_mark_enc, x_dec, x_mark_dec, mask=None):
        del mask
        dec_out = self.forecast(x_enc, x_mark_enc, x_dec, x_mark_dec)
        return dec_out[:, -self.pred_len :, :]


def _infer_e_layers(state_dict: dict) -> int:
    layers: set[int] = set()
    for key in state_dict:
        m = re.match(r"encoder\.attn_layers\.(\d+)\.", key)
        if m:
            layers.add(int(m.group(1)))
    return max(layers) + 1 if layers else 3


def build_dc_itransformer_for_state_dict(state_dict: dict) -> tuple[DCITransformer, DCITransformerConfig]:
    """Build a model with architecture matching *state_dict* (for ``load_state_dict(strict=True)``)."""

    w_emb = state_dict["enc_embedding.value_embedding.weight"]
    seq_len = int(w_emb.shape[1])
    d_model = int(w_emb.shape[0])

    w_proj = state_dict["projection.weight"]
    pred_len = int(w_proj.shape[0])
    d_ff = int(state_dict["encoder.attn_layers.0.conv1.weight"].shape[0])
    enc_in = int(state_dict["local_cnn.0.weight"].shape[0])
    e_layers = _infer_e_layers(state_dict)

    cfg = DCITransformerConfig(
        seq_len=seq_len,
        pred_len=pred_len,
        enc_in=enc_in,
        d_model=d_model,
        n_heads=16,
        e_layers=e_layers,
        d_ff=d_ff,
        factor=1,
        dropout=0.1,
        activation="gelu",
    )
    model = DCITransformer(cfg)
    return model, cfg


def load_dc_itransformer_checkpoint(path: Path, *, map_location: str | torch.device = "cpu") -> tuple[DCITransformer, DCITransformerConfig]:
    raw = torch.load(path, map_location=map_location)
    if not isinstance(raw, dict):
        raise TypeError("checkpoint 应为包含权重键的 dict / OrderedDict。")
    state_dict = raw
    model, cfg = build_dc_itransformer_for_state_dict(state_dict)
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    return model, cfg

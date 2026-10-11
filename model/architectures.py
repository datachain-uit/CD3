"""Prefix-safe temporal backbones for the CQ/LO shared-phase protocol.

Every backbone consumes the same train-fitted tensor ``[batch, phase,
channel]`` and static branch, then emits one set of class logits per observed
prefix.  That common contract is what makes the F1 (recurrent), F2 (PatchTST)
and F3 (MOMENT) comparisons meaningful.
"""
from __future__ import annotations

from pathlib import Path

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence


# These names are persisted in L0/L1 manifests.  Do not infer family labels
# from an arbitrary string at export time.
ARCHITECTURE_METADATA = {
    "rnn": {"model_family": "F1_RECURRENT", "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50"},
    "lstm": {"model_family": "F1_RECURRENT", "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50"},
    "gru": {"model_family": "F1_RECURRENT", "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50"},
    "bilstm": {"model_family": "F1_RECURRENT", "model_revision": "recurrent_shared_phase_v2_4_prefixsafe_epoch50"},
    "patchtst": {"model_family": "F2_TS_TRANSFORMER", "model_revision": "patchtst_shared_phase_v1_prefixsafe"},
    "moment_small": {"model_family": "F3_TS_FOUNDATION", "model_revision": "moment_frozen_linear_probe_v1_prefixsafe"},
    "moment_base": {"model_family": "F3_TS_FOUNDATION", "model_revision": "moment_frozen_linear_probe_v1_prefixsafe"},
}

MOMENT_SPECS = {
    # Weight files were introduced in these immutable repository commits.  At
    # runtime ``snapshot_download`` resolves and records the full commit SHA.
    "moment_small": {"repo_id": "AutonLab/MOMENT-1-small", "revision": "43ee05b", "tier": "small"},
    "moment_base": {"repo_id": "AutonLab/MOMENT-1-base", "revision": "b0ae575", "tier": "base"},
}


def prepare_moment_snapshot(architecture: str, *, cache_dir: str) -> dict:
    """Cache a pinned MOMENT snapshot before measured training begins.

    The returned revision is the full resolved Hub commit, while the cache path
    is deliberately excluded from a run identity because it is host-local.
    """
    if architecture not in MOMENT_SPECS:
        raise ValueError(f"not a MOMENT architecture: {architecture}")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("MOMENT requires huggingface_hub in the model image") from exc
    spec = MOMENT_SPECS[architecture]
    snapshot = snapshot_download(repo_id=spec["repo_id"], revision=spec["revision"], cache_dir=cache_dir)
    return {**spec, "resolved_revision": Path(snapshot).name, "snapshot": str(snapshot)}


class HybridRecurrentClassifier(nn.Module):
    """Temporal P1-P4 branch plus static-feature branch.

    Unlike the older CQ notebook's ``(N, 1, F)`` tensor, this model receives
    true phase sequences ``(N, T, F_dynamic)`` and packs only observed prefix
    phases. Static features are fused after the recurrent encoder, following
    the maintained LO V0-mask baseline.
    """

    def __init__(self, dynamic_dim: int, static_dim: int, num_classes: int,
                 architecture: str, hidden_size: int = 128, num_layers: int = 1,
                 dropout: float = 0.30) -> None:
        super().__init__()
        if architecture not in {"rnn", "lstm", "gru", "bilstm"}:
            raise ValueError("unknown architecture")
        self.architecture = architecture
        self.bidirectional = architecture == "bilstm"
        recurrent_dropout = dropout if num_layers > 1 else 0.0
        if architecture == "rnn":
            self.recurrent = nn.RNN(dynamic_dim, hidden_size, num_layers, batch_first=True,
                                    nonlinearity="tanh", dropout=recurrent_dropout)
        elif architecture in {"lstm", "bilstm"}:
            self.recurrent = nn.LSTM(dynamic_dim, hidden_size, num_layers, batch_first=True,
                                     bidirectional=self.bidirectional, dropout=recurrent_dropout)
        else:
            self.recurrent = nn.GRU(dynamic_dim, hidden_size, num_layers, batch_first=True,
                                    dropout=recurrent_dropout)
        representation_dim = hidden_size * (2 if self.bidirectional else 1)
        self.head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(representation_dim + static_dim, num_classes),
        )

    def forward(self, dynamic_x: torch.Tensor, static_x: torch.Tensor,
                lengths: torch.Tensor) -> torch.Tensor:
        packed = pack_padded_sequence(dynamic_x, lengths.detach().cpu(), batch_first=True,
                                      enforce_sorted=False)
        _, hidden = self.recurrent(packed)
        if self.architecture in {"lstm", "bilstm"}:
            hidden = hidden[0]
        if self.bidirectional:
            final = torch.cat((hidden[-2], hidden[-1]), dim=1)
        else:
            final = hidden[-1]
        return self.head(torch.cat((final, static_x), dim=1))


class SharedPhaseHybridRecurrentClassifier(nn.Module):
    """One recurrent model that emits a prediction after every P1--P4 step.

    This is deliberately separate from :class:`HybridRecurrentClassifier`.
    The latter is retained for local single-prefix smoke tests; this class is
    the experiment implementation used for the paper protocol: one training
    run, one validation-selected checkpoint, four prefix evaluations.
    """

    def __init__(self, dynamic_dim: int, static_dim: int, num_classes: int,
                 architecture: str, hidden_size: int = 128, num_layers: int = 1,
                 dropout: float = 0.30) -> None:
        super().__init__()
        if architecture not in {"rnn", "lstm", "gru", "bilstm"}:
            raise ValueError("unknown architecture")
        self.architecture = architecture
        self.bidirectional = architecture == "bilstm"
        recurrent_dropout = dropout if num_layers > 1 else 0.0
        if architecture == "rnn":
            self.recurrent = nn.RNN(dynamic_dim, hidden_size, num_layers, batch_first=True,
                                    nonlinearity="tanh", dropout=recurrent_dropout)
        elif architecture in {"lstm", "bilstm"}:
            self.recurrent = nn.LSTM(dynamic_dim, hidden_size, num_layers, batch_first=True,
                                     bidirectional=self.bidirectional, dropout=recurrent_dropout)
        else:
            self.recurrent = nn.GRU(dynamic_dim, hidden_size, num_layers, batch_first=True,
                                    dropout=recurrent_dropout)
        representation_dim = hidden_size * (2 if self.bidirectional else 1)
        self.head = nn.Sequential(nn.Dropout(dropout),
                                  nn.Linear(representation_dim + static_dim, num_classes))

    def forward(self, dynamic_x: torch.Tensor, static_x: torch.Tensor) -> torch.Tensor:
        """Return logits of shape ``(batch, timesteps, classes)``.

        At test Pk the caller passes only the P1..Pk prefix. Therefore no
        packing, zero-padding, or future value can influence the prediction.
        """
        if self.bidirectional:
            # A full backward pass at Pk would read P(k+1)..P4.  Evaluate
            # each prefix independently, matching the immutable test prefix.
            steps = []
            for length in range(1, dynamic_x.size(1) + 1):
                prefix, _ = self.recurrent(dynamic_x[:, :length])
                steps.append(prefix[:, -1])
            sequence = torch.stack(steps, dim=1)
        else:
            sequence, _ = self.recurrent(dynamic_x)
        static = static_x.unsqueeze(1).expand(-1, sequence.size(1), -1)
        return self.head(torch.cat((sequence, static), dim=2))


class SharedPhasePatchTSTClassifier(nn.Module):
    """Task-trained PatchTST-style encoder with causal prefix evaluation.

    P1--P4 has only four time points, so the locked F2 configuration uses
    two-phase patches and stride one.  P1 is right-padded inside its patch;
    the padding mask is separate from a numeric zero and no computation for a
    prefix ever receives a later phase.
    """

    def __init__(self, dynamic_dim: int, static_dim: int, num_classes: int,
                 *, hidden_size: int = 128, dropout: float = 0.30,
                 patch_len: int = 2, patch_stride: int = 1,
                 transformer_layers: int = 2, attention_heads: int = 4) -> None:
        super().__init__()
        if patch_len < 1 or patch_stride < 1:
            raise ValueError("PatchTST patch_len and patch_stride must be positive")
        if hidden_size % attention_heads:
            raise ValueError("PatchTST hidden_size must divide attention_heads")
        self.patch_len, self.patch_stride = patch_len, patch_stride
        # A dedicated validity channel distinguishes right-padding from a
        # legitimate scaled zero in a feature value.
        self.patch_projection = nn.Linear((dynamic_dim + 1) * patch_len, hidden_size)
        self.position = nn.Parameter(torch.zeros(1, 4, hidden_size))
        layer = nn.TransformerEncoderLayer(
            d_model=hidden_size, nhead=attention_heads, dim_feedforward=hidden_size * 4,
            dropout=dropout, activation="gelu", batch_first=True, norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=transformer_layers)
        self.norm = nn.LayerNorm(hidden_size)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden_size + static_dim, num_classes))

    def _encode_prefix(self, dynamic_x: torch.Tensor) -> torch.Tensor:
        """Encode exactly the supplied prefix, never a padded future phase."""
        batch, observed_steps, channels = dynamic_x.shape
        steps = observed_steps
        if steps < self.patch_len:
            pad = dynamic_x.new_zeros((batch, self.patch_len - steps, channels))
            dynamic_x = torch.cat((dynamic_x, pad), dim=1)
            steps = self.patch_len
        validity = dynamic_x.new_zeros((batch, steps, 1))
        validity[:, :observed_steps] = 1
        patch_input = torch.cat((dynamic_x, validity), dim=2)
        patches = patch_input.unfold(1, self.patch_len, self.patch_stride)
        # unfold gives [B, n_patches, C+1, patch_len]; flatten in a documented,
        # deterministic channel-then-time order.
        patches = patches.contiguous().reshape(batch, patches.size(1), (channels + 1) * self.patch_len)
        tokens = self.patch_projection(patches)
        if tokens.size(1) > self.position.size(1):
            raise ValueError("PatchTST prefix has more patches than the registered P1-P4 contract")
        tokens = tokens + self.position[:, :tokens.size(1)]
        encoded = self.encoder(tokens)
        return self.norm(encoded.mean(dim=1))

    def forward(self, dynamic_x: torch.Tensor, static_x: torch.Tensor) -> torch.Tensor:
        outputs = []
        for end in range(1, dynamic_x.size(1) + 1):
            temporal = self._encode_prefix(dynamic_x[:, :end])
            outputs.append(self.head(torch.cat((temporal, static_x), dim=1)))
        return torch.stack(outputs, dim=1)


class SharedPhaseMomentClassifier(nn.Module):
    """Frozen official MOMENT encoder plus a trainable static-fusion head.

    The official MOMENT embedding API handles multi-channel tensors.  We keep
    every numeric/mask/timing channel from the common tensor as a channel,
    pad only the *right* side of the observed P1--Pk prefix to its pretrained
    patch length, and pass an explicit time mask.  Encoder weights remain
    frozen; only the task head is optimized (the registered linear-probe mode).
    """

    frozen_backbone = True

    def __init__(self, dynamic_dim: int, static_dim: int, num_classes: int, *,
                 variant: str, dropout: float = .30, cache_dir: str | None = None,
                 resolved_snapshot: str | None = None, backbone_batch_rows: int = 64) -> None:
        super().__init__()
        if variant not in MOMENT_SPECS:
            raise ValueError(f"unknown MOMENT variant: {variant}")
        try:
            from momentfm import MOMENTPipeline
            from huggingface_hub import snapshot_download
        except ImportError as exc:  # Clear remediation rather than a cryptic remote failure.
            raise RuntimeError("MOMENT requires momentfm and huggingface_hub in the model image") from exc
        spec = MOMENT_SPECS[variant]
        snapshot = resolved_snapshot or snapshot_download(
            repo_id=spec["repo_id"], revision=spec["revision"], cache_dir=cache_dir,
        )
        self.backbone_source = {**spec, "snapshot": str(snapshot)}
        self.backbone = MOMENTPipeline.from_pretrained(
            snapshot,
            model_kwargs={"task_name": "embedding"},
            local_files_only=True,
        )
        self.backbone.init()
        for parameter in self.backbone.parameters():
            parameter.requires_grad_(False)
        self.backbone.eval()
        self.backbone_batch_rows = max(1, int(backbone_batch_rows))
        # All published MOMENT-1 variants expose config.d_model.  Fail early
        # if the upstream API changes instead of silently using the wrong head.
        embedding_dim = int(getattr(self.backbone.config, "d_model"))
        self.patch_len = int(getattr(self.backbone.config, "patch_len", 8))
        self.dynamic_dim = dynamic_dim
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(embedding_dim + static_dim, num_classes))

    def train(self, mode: bool = True):
        super().train(mode)
        # Parent ``model.train()`` must never activate dropout or gradients in
        # the frozen pretrained encoder.
        self.backbone.eval()
        return self

    def _embedding(self, dynamic_x: torch.Tensor) -> torch.Tensor:
        batch, steps, channels = dynamic_x.shape
        if channels != self.dynamic_dim:
            raise ValueError("MOMENT channel count differs from fitted shared feature tensor")
        length = max(steps, self.patch_len)
        values = dynamic_x.new_zeros((batch, channels, length))
        values[:, :, :steps] = dynamic_x.transpose(1, 2)
        time_mask = dynamic_x.new_zeros((batch, length))
        time_mask[:, :steps] = 1
        embeddings = []
        # Frozen encoder has no backward requirement. Microbatching avoids
        # materialising B × hundreds-of-channels inside a foundation backbone.
        with torch.no_grad():
            for start in range(0, batch, self.backbone_batch_rows):
                end = min(batch, start + self.backbone_batch_rows)
                output = self.backbone.embed(
                    x_enc=values[start:end], input_mask=time_mask[start:end], reduction="mean"
                )
                embeddings.append(output.embeddings)
        return torch.cat(embeddings, dim=0).to(dtype=dynamic_x.dtype)

    def forward(self, dynamic_x: torch.Tensor, static_x: torch.Tensor) -> torch.Tensor:
        outputs = []
        for end in range(1, dynamic_x.size(1) + 1):
            temporal = self._embedding(dynamic_x[:, :end])
            outputs.append(self.head(torch.cat((temporal, static_x), dim=1)))
        return torch.stack(outputs, dim=1)


def build_shared_phase_model(dynamic_dim: int, static_dim: int, num_classes: int,
                             architecture: str, *, hidden_size: int = 128,
                             num_layers: int = 1, dropout: float = .30,
                             moment_cache_dir: str | None = None,
                             moment_snapshot: str | None = None) -> nn.Module:
    """Build a registered backbone under the common P1--P4 output contract."""
    if architecture in {"rnn", "lstm", "gru", "bilstm"}:
        return SharedPhaseHybridRecurrentClassifier(
            dynamic_dim, static_dim, num_classes, architecture, hidden_size, num_layers, dropout
        )
    if architecture == "patchtst":
        return SharedPhasePatchTSTClassifier(
            dynamic_dim, static_dim, num_classes, hidden_size=hidden_size, dropout=dropout
        )
    if architecture in MOMENT_SPECS:
        return SharedPhaseMomentClassifier(
            dynamic_dim, static_dim, num_classes, variant=architecture, dropout=dropout,
            cache_dir=moment_cache_dir, resolved_snapshot=moment_snapshot,
        )
    raise ValueError(f"unknown shared-phase architecture: {architecture}")

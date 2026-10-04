"""RNN-family hybrid classifiers adapted from TEMPO LO/CQ baselines."""
from __future__ import annotations

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence


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
        sequence, _ = self.recurrent(dynamic_x)
        static = static_x.unsqueeze(1).expand(-1, sequence.size(1), -1)
        return self.head(torch.cat((sequence, static), dim=2))

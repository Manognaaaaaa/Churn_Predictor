"""LSTM (PyTorch) on synthetic temporal sequences.

Caveat (documented in the model card): the dataset has no timestamps, so each
customer's static feature vector is expanded into a short sequence via
Gaussian jitter + feature dropout to emulate monthly variation. The LSTM is a
syllabus demonstration and is expected to land near MLP performance on this
data; with a temporal dataset it would consume real monthly snapshots.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn


class ChurnLSTM(nn.Module):
    def __init__(self, n_features: int, hidden: int = 64):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):            # x: (batch, seq, features)
        out, _ = self.lstm(x)
        return self.head(out[:, -1]).squeeze(-1)


def make_sequences(x: np.ndarray, seq_len: int, noise: np.ndarray, rng) -> np.ndarray:
    """(n, d) -> (n, seq_len, d) with per-step jitter (last step = clean row)."""
    n, d = x.shape
    seqs = np.empty((n, seq_len, d), dtype=np.float32)
    for t in range(seq_len - 1):
        mask = rng.random((n, d)) > 0.1
        seqs[:, t, :] = x + rng.normal(0.0, 1.0, (n, d)) * noise * mask
    seqs[:, -1, :] = x
    return seqs


def train_lstm(x_train: np.ndarray, y_train: np.ndarray, cfg: dict) -> tuple[ChurnLSTM, np.ndarray]:
    params = cfg["models"]["lstm"]
    rng = np.random.default_rng(cfg["seed"])
    torch.manual_seed(cfg["seed"])
    noise = x_train.std(axis=0) + 1e-6
    seqs = make_sequences(x_train, params["seq_len"], noise, rng)
    y = torch.tensor(y_train, dtype=torch.float32)

    model = ChurnLSTM(x_train.shape[1], params["hidden"])
    opt = torch.optim.Adam(model.parameters(), lr=params["lr"])
    loss_fn = nn.BCEWithLogitsLoss()
    ds = torch.utils.data.TensorDataset(torch.tensor(seqs), y)
    loader = torch.utils.data.DataLoader(ds, batch_size=params["batch_size"], shuffle=True)

    model.train()
    for _ in range(params["epochs"]):
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    return model, noise


def predict_lstm(model: ChurnLSTM, x: np.ndarray, noise: np.ndarray,
                 seq_len: int, batch: int = 2048) -> np.ndarray:
    """Deterministic sequences: jitter amplitude zeroed out -> clean last-step signal."""
    model.eval()
    seqs = np.repeat(x[:, None, :], seq_len, axis=1).astype(np.float32)
    preds = []
    with torch.no_grad():
        for i in range(0, len(seqs), batch):
            logits = model(torch.tensor(seqs[i:i + batch]))
            preds.append(torch.sigmoid(logits).numpy())
    return np.concatenate(preds)

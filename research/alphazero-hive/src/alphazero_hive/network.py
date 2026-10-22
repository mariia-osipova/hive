"""Configurable CNN and AlphaZero General NeuralNet adapter."""
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from ._vendor.alpha_zero_general.NeuralNet import NeuralNet
from .encoding import CHANNELS


class HiveCNN(nn.Module):
    def __init__(self, input_channels, action_size, config):
        super().__init__()
        layers, channels = config["layers"], config["channels"]
        if layers not in (4, 6, 8) or channels < 1:
            raise ValueError("CNN needs 4, 6 or 8 layers and positive channels")
        blocks = []
        for index in range(layers):
            blocks.extend((nn.Conv2d(input_channels if index == 0 else channels,
                                     channels, 3, padding=1 if index < 2 else 0),
                           nn.BatchNorm2d(channels), nn.ReLU()))
        self.convolutions = nn.Sequential(*blocks)
        width = 26 - 2 * (layers - 2)
        first, second = config["hidden"]
        self.shared = nn.Sequential(
            nn.Flatten(), nn.Linear(channels * width * width, first),
            nn.BatchNorm1d(first), nn.ReLU(), nn.Dropout(config["dropout"]),
            nn.Linear(first, second), nn.BatchNorm1d(second), nn.ReLU(),
            nn.Dropout(config["dropout"]))
        self.policy = nn.Linear(second, action_size)
        self.value = nn.Linear(second, 1)

    def forward(self, observation):
        features = self.shared(self.convolutions(observation))
        return F.log_softmax(self.policy(features), dim=1), torch.tanh(self.value(features)).flatten()


class HiveNet(NeuralNet):
    def __init__(self, game, config=None):
        self.game = game
        self.config = dict(config if config is not None else game.network_config)
        self.device = torch.device(self.config.get("device", "cpu"))
        self.model = HiveCNN(CHANNELS[game.representation], game.getActionSize(), self.config).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config["learning_rate"])
        self.last_metrics = []

    def predict(self, board):
        observation = self.game.observation(board) if hasattr(board, "native") else board
        self.model.eval()
        with torch.inference_mode():
            inputs = torch.as_tensor(np.asarray(observation)[None], dtype=torch.float32, device=self.device)
            log_policy, value = self.model(inputs)
        return log_policy.exp()[0].cpu().numpy(), float(value.item())

    def train(self, examples):
        if not examples:
            raise ValueError("Cannot train without examples")
        self.model.train()
        self.last_metrics = []
        batch_size = self.config["batch_size"]
        if batch_size < 2:
            raise ValueError("Batch size must be >= 2 for batch normalization")
        for epoch in range(self.config["epochs"]):
            order = np.random.permutation(len(examples))
            policy_sum = value_sum = count = 0
            for start in range(0, len(order), batch_size):
                indices = order[start:start + batch_size].tolist()
                if len(indices) == 1:
                    indices.append(indices[0])
                observations, policies, values = zip(*(examples[i] for i in indices))
                inputs = torch.as_tensor(np.stack(observations), dtype=torch.float32, device=self.device)
                targets = torch.as_tensor(np.stack(policies), dtype=torch.float32, device=self.device)
                # A0G's nonzero terminal-draw sentinel is not a learning reward.
                values = [0.0 if abs(v) < 1e-7 else v for v in values]
                outcomes = torch.as_tensor(values, dtype=torch.float32, device=self.device)
                log_policy, value = self.model(inputs)
                policy_loss = -(targets * log_policy).sum(dim=1).mean()
                value_loss = F.mse_loss(value, outcomes)
                loss = policy_loss + value_loss
                if not torch.isfinite(loss):
                    raise FloatingPointError("Nonfinite training loss")
                self.optimizer.zero_grad(set_to_none=True)
                loss.backward()
                self.optimizer.step()
                n = len(indices)
                policy_sum += policy_loss.item() * n
                value_sum += value_loss.item() * n
                count += n
            self.last_metrics.append({"epoch": epoch + 1, "policy_loss": policy_sum / count,
                                      "value_loss": value_sum / count})

    def payload(self):
        return {"format_version": 1, "config": self.config,
                "representation": self.game.representation, "action_encoding": self.game.codec.encoding,
                "model": self.model.state_dict(), "optimizer": self.optimizer.state_dict()}

    def restore(self, payload):
        if (payload["config"] != self.config or payload["representation"] != self.game.representation or
                payload["action_encoding"] != self.game.codec.encoding):
            raise ValueError("Checkpoint architecture/representation differs from this run")
        self.model.load_state_dict(payload["model"])
        self.optimizer.load_state_dict(payload["optimizer"])

    def save_checkpoint(self, folder="checkpoint", filename="checkpoint.pth.tar"):
        destination = Path(folder) / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        torch.save(self.payload(), temporary)
        temporary.replace(destination)

    def load_checkpoint(self, folder="checkpoint", filename="checkpoint.pth.tar"):
        payload = torch.load(Path(folder) / filename, map_location=self.device, weights_only=True)
        self.restore(payload)

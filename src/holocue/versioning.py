"""Monotonic snapshot admission after command acknowledgements."""

from dataclasses import dataclass


@dataclass
class VersionGate:
    required_revision: int = -1
    required_epoch: int = -1
    revision: int = -1
    epoch: int = -1

    def require(self, revision: int, epoch: int):
        self.required_revision = max(self.required_revision, revision)
        self.required_epoch = max(self.required_epoch, epoch)

    def admit(self, revision: int, epoch: int) -> bool:
        if revision < max(self.required_revision, self.revision):
            return False
        if epoch < max(self.required_epoch, self.epoch):
            return False
        self.revision = revision
        self.epoch = epoch
        return True

    def current(self, revision: int, epoch: int) -> bool:
        return revision >= self.required_revision and epoch >= self.required_epoch

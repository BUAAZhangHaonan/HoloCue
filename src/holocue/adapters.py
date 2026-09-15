"""Future intranet adapter contract. Phase 1 only exports versioned scene-space packets."""
from typing import Protocol
from .models import DisplayPacket

class HolographyAdapter(Protocol):
    def capabilities(self)->dict: ...
    def submit(self,packet:DisplayPacket)->dict: ...
    def cancel(self,session_id:str,epoch:int)->None: ...

def require_optical_calibration(packet:DisplayPacket)->None:
    if packet.renderer_kind!='calibrated_optical':
        raise ValueError('Real optical execution requires a measured calibration profile')
    if any(c.sigma_units!='m' for c in packet.cues):
        raise ValueError('Real optical sigma values must be expressed in metres')

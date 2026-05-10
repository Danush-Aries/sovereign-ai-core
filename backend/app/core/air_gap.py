import os
import socket
from typing import Optional

class AirGapController:
    """
    The Air-Gap Kill-Switch.
    Intercepts socket creation to block all outbound traffic in Sovereign Mode.
    """
    def __init__(self):
        self.sovereign_mode = False

    def toggle_sovereign_mode(self, enabled: bool):
        self.sovereign_mode = enabled
        print(f"Sovereign Mode {'ENABLED' if enabled else 'DISABLED'}. Network lock: {enabled}")

    def intercept_socket(self, family, type, proto, flags):
        if self.sovereign_mode:
            raise PermissionError("Sovereign Mode Active: Outbound network traffic is strictly prohibited.")
        return socket.socket(family, type, proto)

# Global Controller Instance
AirGap = AirGapController()

# Monkey-patch socket for total isolation
socket.socket = AirGap.intercept_socket

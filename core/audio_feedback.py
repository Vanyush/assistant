import subprocess
from pathlib import Path


class AudioFeedback:

    def __init__(self):
        self.activation_sound = (
            Path(__file__).parent.parent
            / "assets"
            / "sounds"
            / "activation.wav"
        )

    def play_activation(self):
        subprocess.Popen(
            [
                "paplay",
                str(self.activation_sound)
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
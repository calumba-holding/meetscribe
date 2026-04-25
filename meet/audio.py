"""Backward-compat shim — audio helpers live in `meetscribe-record` since 0.5.0.

Re-exports all public names from `meet_record.audio`.
"""

from meet_record.audio import *  # noqa: F401,F403
from meet_record.audio import (  # noqa: F401  re-exported names
    StereoChannels,
    read_stereo_channels,
    compress_audio,
    compute_speaker_channel_energy,
)

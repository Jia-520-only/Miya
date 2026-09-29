"""One lock for the camera hardware.

DirectShow has no idea that several of our threads want the same devices. When
two of them try to open a camera at once the second attempt does not fail fast -
it blocks, sometimes for minutes, and it takes the calling thread with it.

That is not theoretical. A thread dump taken while Miya's observation loop had
been silent for five minutes showed **ten** threads inside camera open and probe
code at the same moment: the inventory probe, a persistent reader, one-shot
captures and the desktop panel's polling had all piled up on the same USB bus.
The observation loop was simply queued behind them, and her eyes stopped.

So every operation that touches a camera device takes this lock. It is reentrant,
because a capture legitimately opens a device and then reads from it. It is
deliberately *not* held while a persistent reader sits in its read loop - that
thread owns its device by design, and holding the lock for its lifetime would
stop everything else from ever running.
"""

from __future__ import annotations

import threading

# Reentrant: open_camera() is called both directly and from capture_camera_frame(),
# and the inner call must not deadlock against the outer one.
HARDWARE_LOCK = threading.RLock()

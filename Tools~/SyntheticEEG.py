"""Explicit synthetic EEG-like test signal. NOT measured human EEG."""
import math
import time
from pylsl import StreamInfo, StreamOutlet, local_clock

RATE = 250
info = StreamInfo("SIMULATED_EEG_TEST", "EEG", 4, RATE, "double64", "standalonelsl-synthetic-eeg")
info.desc().append_child_value("manufacturer", "SYNTHETIC TEST ONLY - NO EEG HARDWARE")
channels = info.desc().append_child("channels")
for label in ("TestFz", "TestCz", "TestPz", "TestOz"):
    channel = channels.append_child("channel")
    channel.append_child_value("label", label)
    channel.append_child_value("unit", "microvolts")
    channel.append_child_value("type", "EEG")
outlet = StreamOutlet(info)
print("Sending SIMULATED_EEG_TEST: 4 channels, 250 Hz. NOT real EEG. Ctrl+C to stop.")
origin = local_clock()
index = 0
try:
    while True:
        timestamp = origin + index / RATE
        remaining = timestamp - local_clock()
        if remaining > 0:
            time.sleep(remaining)
        now = local_clock()
        if now - timestamp > 0.25:
            # Report scheduling gaps rather than fabricate an unlimited catch-up backlog.
            print("Sender scheduling gap: %.3f s" % (now - timestamp))
            index = int((now - origin) * RATE)
            continue
        signal_time = timestamp - origin
        values = [20 * math.sin(2 * math.pi * (8 + ch) * signal_time) for ch in range(4)]
        outlet.push_sample(values, timestamp)
        index += 1
except KeyboardInterrupt:
    print("Synthetic EEG sender stopped.")

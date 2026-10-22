# StandaloneLSL — How to use

**Package:** com.unitylsl.bridge · **Version:** 1.0.0 · **Author:** Shad Ahmed

## Install in Unity

In **Window > Package Manager**, choose **+ > Install package from git URL** and enter:

```text
https://github.com/user-shiam/unitylslbridge.git#v1.0.0
```

This installs the public compiled package without the separate implementation source repository. Use `#main` instead of `#v1.0.0` to follow the latest published branch when updating the package.

Alternatively install a downloaded package from disk:

1. Download/extract the package and keep its contents together. The enclosing folder can have any name.
2. Open **Window > Package Manager**.
3. Choose **+ > Install package from disk** (called Add package from disk in some versions).
4. Select **package.json in the extracted package root**.

Install it once in each Unity project where you want to use LSL.

The package targets Unity 6, Windows x64 and Android ARM64. Other platforms need compatible native libraries. Python is not required by the Unity runtime.

The public package repository is [user-shiam/unitylslbridge](https://github.com/user-shiam/unitylslbridge). The package files are at its root.

## Send markers from C#

Create `SendLsl.cs` in your Unity project's Assets folder, paste this code, and attach it to an active GameObject:

```csharp
using UnityEngine;
using StandaloneLSL;

public class SendLsl : MonoBehaviour
{
    LslSession session;
    QuestLslOutlet outlet;
    float nextSend;

    void Start()
    {
        session = new LslSession();
        outlet = session.CreateOutlet("MyMarkers");
    }

    void Update()
    {
        if (outlet == null || Time.unscaledTime < nextSend) return;
        nextSend = Time.unscaledTime + 5;
        outlet.PushMarker("TEST", QuestLslOutlet.LocalClock);
    }

    void OnDestroy() { session?.Dispose(); }
}
```

Press Play on Windows, or run your Android build. Open LabRecorder on the PC, click Update, and select **MyMarkers**. The script sends TEST every five seconds. Sender and receiver must be on a network allowing LSL communication; keep Android awake/in the foreground for initial tests.

For a real event, call `outlet.PushMarker("TRIAL_START", QuestLslOutlet.LocalClock)` from your own event handler. A successful send means liblsl accepted it; confirm reception on the other device.

## Send numerical data

Create a separate Float32 outlet and send matching arrays:

```csharp
var values = session.CreateOutlet("MyValues", "Data", 3, 90,
    QuestLslChannelFormat.Float32);
values.PushFloats(new float[] { 1, 2, 3 }, QuestLslOutlet.LocalClock);
```

This declares three channels at an expected 90 samples/second; your code must send at the actual required rate. Use nominalRate 0 for irregular sampling. You can create multiple outlets per session. Disposing the session closes its streams.

## Receive markers from C#

Create `ReceiveLsl.cs`, attach it to an active GameObject, and change MyMarkers to the incoming stream name:

```csharp
using System;
using UnityEngine;
using StandaloneLSL;

public class ReceiveLsl : MonoBehaviour
{
    LslSession session;
    QuestLslInlet inlet;
    string[] sample;

    async void Start()
    {
        session = new LslSession();
        try
        {
            inlet = await session.ConnectAsync("name", "MyMarkers", 10);
            if (inlet.Format != QuestLslChannelFormat.String)
                throw new NotSupportedException("Use TryPullFloats for Float32.");
            sample = new string[inlet.ChannelCount];
        }
        catch (OperationCanceledException) { }
        catch (Exception error) { Debug.LogException(error); }
    }

    void Update()
    {
        if (inlet == null || sample == null) return;
        try
        {
            for (int n = 0; n < 32 && inlet.TryPullStrings(sample, out double time); n++)
                Debug.Log($"{time}: {sample[0]}");
        }
        catch (Exception error) { Debug.LogException(error); inlet = null; }
    }

    void OnDestroy() { session?.Dispose(); }
}
```

For a Float32 stream use a `float[inlet.ChannelCount]` buffer and `TryPullFloats(buffer, out timestamp)`. Use `TryPullDoubles(double[], out timestamp)` for Float64 or Float32/Int32/Int16/Int8 numeric input. Int64 is not supported. The EEG device needs its own LSL outlet/bridge. Receiving is polled from Update, so your Unity handling runs on the main thread. ConnectAsync times out if the stream cannot be opened.

Incoming timestamps belong to the sender's clock. To compare them with local LSL timestamps, obtain `inlet.GetTimeCorrection(timeoutSeconds)` and add the offset. The initial estimate can block/time out; avoid waiting for it in Update.

Use the buffer only when a `TryPull...` call returns true. After a false return its contents are undefined (IL2CPP may overwrite them with zeros), so copy the values you want to keep.

## Stimulus timing for EEG

`QuestLslOutlet.LocalClock` is the time your code runs. A visual stimulus enabled in that frame appears on the display roughly 10-20 ms later. For stimulus markers use the frame's predicted display time instead:

```csharp
stimulus.SetActive(true);
outlet.PushMarker("STIM_ON", QuestLslDisplayClock.PredictedDisplayTime);
```

Call it on Unity's main thread in the frame the stimulus becomes visible; all calls in one frame return the same value. It uses the Meta runtime's display prediction (`QuestLslDisplayClock.IsPredicted` is then true). Without the Meta XR SDK, in the Editor or on Windows it returns `LocalClock + QuestLslDisplayClock.FallbackLatencySeconds` (default 0). `QuestLslPublisher` stamps its pose samples this way and offers `SendStimulusMarker`. Keep button/response markers on `LocalClock`; input is read when your code runs.

The prediction is the runtime's estimate. Verify the remaining offset once per setup with a photodiode on the lens recorded by the EEG amplifier: add `QuestLslPhotodiodePatch` to a GameObject, and call `QuestLslPhotodiodePatch.Current?.Flash(outlet, "STIM_ON")` (or `Flash()` next to your own display-time marker). A small head-locked square turns from black to white in exactly that frame. Place the photodiode over it, record the photodiode on an AUX channel, and compare each white edge with its marker; the median difference is the remaining offset, the spread is the jitter. Remove the patch for real sessions. Dropped frames delay a stimulus by one frame; keep the scene at a steady frame rate. A higher refresh rate (e.g. 120 Hz on Quest 3) shortens the input sampling interval.

## Record selected data from C#

Inside your own component, create a recorder when recording begins:

```csharp
string path = System.IO.Path.Combine(Application.persistentDataPath,
    "trial-" + DateTime.UtcNow.Ticks + ".jsonl");
var recording = new LslRecorder(path);
recording.RecordMarker("MyMarkers", "TRIAL_START", QuestLslOutlet.LocalClock);
// Later: recording.RecordFloats(streamName, values, timestamp);
recording.Stop(); // flushes and closes the file
```

Keep the recorder in a field to record multiple samples over time, and dispose it in OnDestroy. You choose which sent/received samples to record. The directory must exist; existing files are not overwritten by default. Received timestamps should use an explicit clock label, e.g. `RecordStrings("Remote", sample, time, "remote:device")`.

Files are JSON Lines, not XDF. For XDF use LabRecorder on the PC. For high-rate recording, use your own bounded worker queue so disk writes do not stall Unity frames.

## Android / Quest settings

### Ready-to-use EEG acquisition

Add `StandaloneEegReceiver` to a GameObject and call its public C# API:

```csharp
var eeg = gameObject.AddComponent<StandaloneEegReceiver>();
eeg.SampleReceived += sample => Debug.Log(sample.RemoteTimestamp);
eeg.StartAcquisition(new EegAcquisitionOptions {
    property = "type", value = "EEG", record = true,
    recordingDirectory = System.IO.Path.Combine(Application.persistentDataPath, "EEG")
});
// Later: eeg.StopAcquisition();
```

It discovers/connects in a worker, reads source metadata, receives numeric samples into double arrays, records raw data and retries after a no-data timeout. SampleReceived is dispatched on Unity's main thread through a bounded preview queue; raw recording occurs before that queue. Check `eeg.Acquisition.Status`, `LastError`, `SamplesReceived`, `PreviewSamplesDropped`, `Metadata` and `RecordingPath` from your C# code. Queue overflow can omit preview events without discarding already-recorded samples. Native/network buffers are still finite; inspect continuity in sustained tests.

Use a unique name or source_id instead of type EEG when multiple EEG streams exist. No physical EEG comes from the Quest itself: an external device/bridge must publish it. Float32, Float64 and supported integer data are accepted; source units/labels are retained in metadata without assumed unit conversion.

Recordings are .jsonl plus .metadata.xml files. Raw sample timestamps stay in the source clock. Separate clock_correction rows store [offset, remote_time, round_trip_uncertainty] in seconds, with a local LSL timestamp. Preview LocalTimestamp equals remote timestamp + estimated offset, or NaN while synchronization is pending. The network estimate is not a guarantee of EEG-to-display alignment. Float64 JSON uses explicit strings for NaN/Infinity values.

Use the StandaloneEegReceiver example above in your own Unity component. Display acquisition status using your own UI. For a hardware-free test use the included Tools~/SyntheticEEG.py sender as described below. Keep only one matching EEG source active or select a unique source_id.

Start/stop the Unity wrapper on the main thread. Stop briefly waits for bounded native cancellation/cleanup and disk flush. Advanced callers can use EegAcquisition directly and await StopAsync, holding Android multicast access themselves. Source acquisition options are snapshotted at start; stop/restart to change them.

- Install Unity Android Build Support; select IL2CPP, ARM64, minimum Android API 29.
- Set Internet Access to Require. Wi-Fi/multicast permissions come with this package.
- Use **Tools > StandaloneLSL > Check Native Setup**.
- Quest additionally requires working Android OpenXR and XR interactions. An Android phone test can run without XR.

Optional Android marker autostart reads Assets/Resources/QuestLslSettings.json. For example: {"enabled":true,"streamPrefix":"Quest","heartbeatSeconds":5}. Without this file, create your own streams explicitly from C#.

Windows x64 sending/receiving and recording tests passed. Android/Quest EEG reception, status visibility, clock estimation and sustained recording still require device testing. This plugin does not include media codecs or playback.

## Optional PC EEG test — no EEG headset needed

**Python and pylsl are only required for this optional PC test sender. Unity and Quest do not need Python.** A real EEG device needs its own working LSL bridge; pylsl is not automatically required for that bridge.

Download/extract the package on the PC that will send the test data. Open PowerShell in its package root (the folder containing package.json and README.md), then run:

```powershell
py -m pip install pylsl
py ".\Tools~\SyntheticEEG.py"
```

On systems using the python command instead of py, use python for both commands. If pylsl reports that its native liblsl library is missing on Windows, this package includes a compatible Windows x64 library. Using 64-bit Python, set its path before starting the sender:

```powershell
$env:PYLSL_LIB = (Resolve-Path ".\Plugins\x86_64\lsl.dll").Path
py ".\Tools~\SyntheticEEG.py"
```

See the [official pylsl installation and library-loading instructions](https://github.com/labstreaminglayer/pylsl#installation) for other Python/platform combinations.

Keep the PC sender running. It publishes **SIMULATED_EEG_TEST**, type EEG, four channels at 250 Hz. This is generated test data, not measured human EEG. Press Ctrl+C to stop it.

In your Unity receiver's StartAcquisition options use:

```csharp
property = "source_id",
value = "standalonelsl-synthetic-eeg"
```

Connect the PC and Quest to the same suitable network and run your built Quest app. Your C# code should report Acquisition.Status as Streaming, Metadata.ChannelCount as 4, Metadata.NominalRate as 250, and an increasing SamplesReceived count. Run the receiver code once; installing the plugin alone does not start acquisition. Stop/restart the sender to test reconnection. Allow LSL networking on the PC's private-network firewall; guest-network isolation can block discovery.

With record enabled, the Quest receiver creates JSONL plus metadata XML files in the directory supplied by your C# code. For example use Path.Combine(Application.persistentDataPath, "EEG"). Retrieve those files after a normal stop and inspect samples/timestamps. For a real EEG test, replace the synthetic source_id with the actual device stream identity. Use LabRecorder on the PC to record the EEG stream and Unity marker stream into XDF.

The script is included in the package. If installed through Unity Package Manager, download/extract a copy to any convenient PC directory before following these commands, or run them from the installed package's resolved directory. All commands use paths relative to the package root.

## Files in this folder

- Runtime: compiled C# API.
- Editor: Unity setup menu.
- Plugins: Android/Windows native libraries and permissions.
- Tools~/SyntheticEEG.py: optional PC test sender. The ~ folder is ignored by Unity's asset importer.
- package.json: Unity installation manifest.
- LICENSE and THIRD-PARTY-NOTICES.txt: required license notices.
- .meta files: Unity asset identities/import settings. Keep them with their files; you do not open them manually.

## Implementation source

This is a complete compiled distribution. Editable C#/native implementation and build tools are maintained separately and are not required to install or use the package. Consult the package distributor for implementation-source availability. The included Python test sender is a runnable example, not the plugin implementation.

## Credits and references

**StandaloneLSL package author and maintainer: Shad Ahmed.** The package adds Unity C# integration, stream lifecycle management, EEG acquisition workflows and JSONL recording on top of the LSL native library.

- **Native dependency:** [Lab Streaming Layer / liblsl](https://github.com/sccn/liblsl) provides stream discovery, network transport, buffering and clock synchronization. Its upstream authors retain their copyright and license.
- **Optional Python test dependency:** [pylsl](https://github.com/labstreaminglayer/pylsl) provides the Python LSL interface used by the included synthetic sender.
- **Unity integration reference:** [LSL4Unity](https://github.com/labstreaminglayer/LSL4Unity).
- **Standalone Quest data-capture reference:** [luisqtr/data-capture-vr](https://github.com/luisqtr/data-capture-vr).

The last two links identify reference projects, not bundled runtime dependencies. Their original scenes and experiment logic are not included. Third-party licenses and copyright notices are preserved in THIRD-PARTY-NOTICES.txt; the package's own license is in LICENSE.

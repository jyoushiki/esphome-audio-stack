# P4 recovery checkpoint, 2026-09-05

The full landscape JPEG profile preserves the measured main performance while
updating codec control to esp_codec_dev 1.6.2. The adapter supplies the native
I2C controller identity and 8-bit write address required by the codec reference
manager, and enables the I2S channels before codec open. TDM geometry, clocks,
audio buffers, task placement and media hot loops retain the main implementation.

The code requires a native I2C controller for hardware codecs. Configuration
validation reports an incompatible bus type before C++ generation.

## Measured environment

- ESP32-P4 revision 1.3, full landscape JPEG, speaker volume 1 percent.
- ESPHome 2026.8.2 and ESP-IDF 5.5.5.
- esp_codec_dev 1.6.2, ESP-SR 2.5.3, esp_audio_effects 1.3.0~1, ESP-DSP 1.8.0.
- Effects 1.4+ requires P4 revision 3.0. Supported newer targets select the
  current 1.4 line; pre-v3 P4 selects the newest supported 1.3 line.
- Intercom: 6344bb2c096c78ddfe4a6cf3470e786a86d7615c.
- VoIP: 61eebe5abc497f04cb659ee98482c23d05ad035c.
- Runtime Controller: eba7ee3e75f812cc1f09bc1c3217084358d62ba2.
- Camera: 47d47104e73c692e72175efd60e2493b04bfa0cc.
- Firmware compilation identity: 2026-09-05 21:06:59 +0000.
- OTA SHA-256: db9b53e47f625247df6ae66a7533556e2ad52b7d26bee3206dc7a14f34aaf762.

## Hardware comparison

Direct SIP calls use bidirectional L16/16000/1 audio with 10 ms packets.
Each video scenario lasts approximately 30 seconds. Camera output is 800x800.

| Incoming JPEG | Terminating side | Main panel FPS | Updated panel FPS | Main camera FPS | Updated camera FPS |
|---|---|---:|---:|---:|---:|
| 320x180 | Peer | 9.70 | 9.80 | 4.27 | 4.37 |
| 320x180 | P4 | 9.83 | 9.73 | 4.40 | 4.33 |
| 800x800 | Peer | 7.23 | 7.10 | 1.57 | 1.57 |

All three video calls and a 16-second audio-only call completed without watchdog
or missing RTP audio samples. Home Assistant call resources returned to zero.
The small FPS differences are within the variation observed in these short runs.

Seventeen audio contract tests passed and the full P4 firmware compiled.
S3 code generation selects effects 1.4.2 and codec_dev 1.6.2; S3 hardware has not
been qualified at this checkpoint.

Panel measurements use completed presentation counters. RTP WAV continuity does
not independently prove physical DAC/speaker playback. These direct-peer tests
do not qualify HA/card/trunk routes, H264, or future SIP/Opus changes.

## Next experiment

Preserve this source checkpoint and its firmware as the rollback reference.
Evaluate current stable dependencies and relevant new options in an isolated
candidate, using the same benchmark. Restore this firmware if performance or
stability regresses. Remaining dependency updates, SIP interoperability, Opus
and the direct/HA-transcoding UI attribute are still pending.

# Third-Party Notices

Project code in this repository is MIT-licensed unless a file states otherwise.

ESPHome firmware builds resolve most Espressif dependencies through the IDF
Component Manager when the corresponding YAML feature is used:

| Component | Used by |
|---|---|
| `espressif/esp_audio_effects` | Rate, bit-depth and channel conversion. |
| `espressif/esp_codec_dev` | Hardware codec control and codec-backed I2S. |
| `espressif/esp-dsp`, `espressif/esp-sr` | Standalone AEC and AFE support. |
| `espressif/gmf_ai_audio` | Single-mic and dual-mic GMF-backed AFE pipeline. ESPHome fetches `elements/gmf_ai_audio` from `https://github.com/n-IA-hane/esp-gmf.git` at ref `43b1e18f2a9234393a65d4b7eba2f132b95a5a24`; it is not vendored in this repository. |

Their upstream licenses apply. Firmware using Espressif-restricted components is
intended for Espressif products/SoCs.

The fetched `gmf_ai_audio` source carries the license terms in its upstream/fork
tree, including Espressif product-use restrictions where applicable. Review and
redistribute those notices with any firmware or source distribution that
includes the dependency.

The `esphome/components/resampler` adapter derives from ESPHome. Its C++ code
retains the upstream GPLv3 terms and its Python code retains the upstream MIT
terms, as recorded in that directory's `LICENSE` and `UPSTREAM.md`. These
upstream terms apply instead of the repository's default MIT notice.

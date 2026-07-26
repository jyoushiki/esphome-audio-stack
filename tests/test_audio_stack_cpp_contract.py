#!/usr/bin/env python3
"""Static contract checks for ESP Audio Stack hot paths."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_STACK = ROOT / "esphome" / "components" / "esp_audio_stack"


def read(name: str) -> str:
    return (AUDIO_STACK / name).read_text(encoding="utf-8")


def test_tdm_16bit_rx_extracts_only_selected_channels() -> None:
    cpp = read("audio_effects_rate_converter.cpp")

    prepare = cpp[cpp.index("bool prepare(") : cpp.index("bool process_multi(", cpp.index("bool prepare("))]
    assert "const uint8_t deintlv_channels = source_32bit ? source_channels : nch;" in prepare
    assert "ensure_deintlv_buffers_(deintlv_channels, in_count)" in prepare

    deinterleave = cpp[cpp.index("bool deinterleave_selected_(") : cpp.index("bool extract_selected_channels_(")]
    assert "ensure_deintlv_buffers_(static_cast<uint8_t>(stride), in_count)" in deinterleave
    assert "return this->extract_selected_channels_" in deinterleave

    extract = cpp[cpp.index("bool extract_selected_channels_(") : cpp.index("bool ensure_bit_conversion_(")]
    assert "ensure_deintlv_buffers_(this->channels_, in_count)" in extract
    assert "out[i] = in[i * stride + offset];" in extract


def test_realtime_audio_loop_has_no_tick_delay_or_effect_allocator() -> None:
    cpp = read("audio_pipeline.cpp")
    alc = cpp[
        cpp.index("bool ESPAudioStack::apply_mic_alc_gain_(") :
        cpp.index("\n#ifdef USE_ESP_AUDIO_STACK_MONO_REF", cpp.index("bool ESPAudioStack::apply_mic_alc_gain_("))
    ]
    converter = cpp[
        cpp.index("bool ESPAudioStack::tx_bit_cvt_16_to_32_(") :
        cpp.index("\n#endif", cpp.index("bool ESPAudioStack::tx_bit_cvt_16_to_32_("))
    ]
    cold_allocate = cpp[
        cpp.index("bool ESPAudioStack::allocate_audio_buffers_(") :
        cpp.index("\nvoid ESPAudioStack::preallocate_audio_buffers_from_task_", cpp.index("bool ESPAudioStack::allocate_audio_buffers_("))
    ]

    assert "vTaskDelay(" not in cpp
    assert "esp_ae_alc_open" not in alc
    assert "esp_ae_alc_close" not in alc
    assert "esp_ae_bit_cvt_open" not in converter
    assert "esp_ae_bit_cvt_close" not in converter
    assert "esp_ae_alc_open" in cold_allocate
    assert "esp_ae_bit_cvt_open" in cold_allocate
    assert "frame_interval_avg_us" in cpp
    assert "t_frame_interval_max_us" in cpp


def test_idle_tx_completion_overflow_preserves_full_duplex_capture() -> None:
    """Clock-only DMA callbacks may outpace the audio task during Wi-Fi startup."""
    cpp = read("esp_audio_stack.cpp")
    header = read("esp_audio_stack.h")
    callback = cpp[
        cpp.index("bool IRAM_ATTR ESPAudioStack::tx_on_sent_callback") :
        cpp.index("bool ESPAudioStack::prepare_tx_completion_tracking_")
    ]

    assert "tx_completion_idle_event_drops_" in header
    assert "tx_completion_pending_real_records_.load" in callback
    assert "self->tx_completion_desync_ = true" in callback
    assert "self->tx_completion_idle_event_drops_.fetch_add" in callback
    assert "Discarded %u idle TX completion events" in cpp


def test_speaker_output_callbacks_follow_i2s_completion_not_buffer_acceptance() -> None:
    """Sendspin/mixer timing must advance only after DMA reports playback."""
    stack_cpp = read("esp_audio_stack.cpp")
    pipeline_cpp = read("audio_pipeline.cpp")
    speaker_cpp = read("speaker/esp_audio_stack_speaker.cpp")

    dma_callback = stack_cpp[
        stack_cpp.index("bool IRAM_ATTR ESPAudioStack::tx_on_sent_callback") :
        stack_cpp.index("bool ESPAudioStack::prepare_tx_completion_tracking_")
    ]
    completion_drain = stack_cpp[
        stack_cpp.index("void ESPAudioStack::drain_tx_completion_events_") :
        stack_cpp.index("bool ESPAudioStack::queue_tx_completion_record_")
    ]
    dma_write = pipeline_cpp[
        pipeline_cpp.index("bool ESPAudioStack::write_tx_dma_blocks_") :
        pipeline_cpp.index("void ESPAudioStack::process_tx_clock_only_")
    ]
    public_play = speaker_cpp[
        speaker_cpp.index("size_t ESPAudioStackSpeaker::play(const uint8_t *data, size_t length)") :
        speaker_cpp.index("bool ESPAudioStackSpeaker::has_buffered_data()")
    ]

    assert "add_speaker_output_callback" in speaker_cpp
    assert "audio_output_callback_.call(frames, timestamp)" in speaker_cpp
    assert "xQueueSendToBackFromISR" in dma_callback
    assert "dispatch_speaker_output_callbacks_" in completion_drain
    assert "record.real_frames" in completion_drain
    assert "record.trailing_silence_frames" in completion_drain

    # Every real write is paired with its completion record before submission
    # to IDF. Merely accepting bytes into the public speaker buffer must not
    # advance Sendspin/mixer playback time.
    assert dma_write.index("queue_tx_completion_record_(record)") < dma_write.index(
        "write_tx_frame_(ctx, bytes + offset"
    )
    assert "dispatch_speaker_output_callbacks_" not in dma_write
    assert "audio_output_callback_" not in public_play


def test_failed_tx_write_cannot_leave_stale_completion_metadata() -> None:
    """A reserved DMA record must never be consumed by a later successful write."""
    pipeline_cpp = read("audio_pipeline.cpp")
    dma_write = pipeline_cpp[
        pipeline_cpp.index("bool ESPAudioStack::write_tx_dma_blocks_") :
        pipeline_cpp.index("void ESPAudioStack::process_tx_clock_only_")
    ]

    # The record must remain queued before the blocking IDF write: on_sent may
    # run before i2s_channel_write() returns. If the write then fails, however,
    # tracking is irrecoverably ambiguous and the pipeline must stop instead of
    # letting a later DMA completion consume stale metadata.
    assert dma_write.index("queue_tx_completion_record_(record)") < dma_write.index(
        "write_tx_frame_(ctx, bytes + offset"
    )
    assert dma_write.count("mark_tx_completion_desync_") == 2
    assert "if (!this->write_tx_frame_(ctx, tx_data, tx_bytes))" in dma_write
    assert "if (!this->write_tx_frame_(ctx, bytes + offset" in dma_write

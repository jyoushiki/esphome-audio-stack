"""Initial and runtime VAD changes share the existing configuration owner."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_vad_waits_for_open_and_never_overwrites_a_newer_setting(tmp_path):
    source = (ROOT / "esphome/components/esp_afe/esp_afe.cpp").read_text()
    methods = ""
    for name in ("set_vad_enabled_runtime_", "apply_pending_gmf_vad_state_"):
        start = source.index("bool EspAfe::" + name)
        methods += source[start:source.index("\n}\n", start) + 2] + "\n"
    harness = r'''
#include <atomic>
#include <cassert>
#define USE_ESP_AFE_GMF_PATH
template<class... T> void log(T...) {}
#define ESP_LOGI(...) log(__VA_ARGS__)
#define ESP_LOGW(...) log(__VA_ARGS__)
constexpr const char *TAG="vad";
constexpr int CONFIG_MUTEX_TIMEOUT=10,ESP_AFE_FEATURE_VAD=1;
using esp_gmf_err_t=int;
bool lock_available=true,hardware_vad=true;int manager_result=0,manager_calls=0;
namespace esp_audio_stack {
struct ScopedLock {bool acquired;ScopedLock(void*,int):acquired(lock_available){} explicit operator bool()const{return acquired;}};
}
int esp_gmf_afe_manager_enable_features(void*,int,bool enabled) {
 ++manager_calls;if(manager_result>=0)hardware_vad=enabled;return manager_result;
}
struct EspAfe {
 std::atomic<bool> vad_enabled_{true},voice_present_{true},afe_stopped_{false},gmf_vad_state_pending_{true};
 void *config_mutex_=this,*afe_manager_=this;
 bool is_initialized()const{return true;}
 bool all_features_disabled_()const{return false;}
 bool recreate_instance_(bool){return true;}
 bool set_vad_enabled_runtime_(bool);
 bool apply_pending_gmf_vad_state_();
};
'''
    checks = r'''
int main(){
 EspAfe afe;
 // Toggle before asynchronous open must leave structural VAD intact.
 assert(afe.set_vad_enabled_runtime_(false));assert(hardware_vad && manager_calls==0);
 assert(!afe.voice_present_ && afe.gmf_vad_state_pending_);
 lock_available=false;assert(!afe.apply_pending_gmf_vad_state_());
 assert(afe.gmf_vad_state_pending_ && manager_calls==0);
 lock_available=true;assert(afe.set_vad_enabled_runtime_(true));
 assert(afe.apply_pending_gmf_vad_state_());assert(hardware_vad && manager_calls==0);
 assert(!afe.gmf_vad_state_pending_);
 assert(afe.set_vad_enabled_runtime_(false));assert(!hardware_vad && manager_calls==1);
 // A failed initial disable is retried, without claiming it was applied.
 afe.gmf_vad_state_pending_=true;hardware_vad=true;manager_result=-1;
 assert(!afe.apply_pending_gmf_vad_state_());assert(afe.gmf_vad_state_pending_ && hardware_vad);
 manager_result=0;assert(afe.apply_pending_gmf_vad_state_());assert(!hardware_vad);
}
'''
    cpp = tmp_path / "vad.cpp"
    cpp.write_text(harness + methods + checks)
    exe = tmp_path / "vad"
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

"""Exercise the actual quantum adapter and the compile-time selection policy."""

import importlib.util
from pathlib import Path
import subprocess

import pytest
from esphome import config_validation as cv
from esphome.core import ID
import esphome.final_validate as fv

ROOT = Path(__file__).resolve().parents[1]
AFE = ROOT / "esphome/components/esp_afe"
spec = importlib.util.spec_from_file_location("post_agc_schema", AFE / "__init__.py")
schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema)


@pytest.fixture(autouse=True)
def final_validation_context():
    token = fv.full_config.set({})
    yield
    fv.full_config.reset(token)


@pytest.mark.parametrize("mics,initial,switch,support,expected", [
    (1, True, True, "auto", False),
    (2, False, False, "auto", False),
    (2, True, False, "auto", True),
    (2, False, True, "auto", True),
    (2, False, False, True, True),
    (2, False, False, False, False),
    (2, True, False, False, None),
    (2, False, True, False, None),
])
def test_post_agc_is_compiled_only_when_required(monkeypatch, mics, initial, switch, support, expected):
    afe_id = ID("test_afe")
    fv.full_config.set({"switch": [
        {"platform": "esp_afe", "esp_afe_id": afe_id, **({"agc": {}} if switch else {})},
        {"platform": "esp_afe", "esp_afe_id": ID("another_afe"), "agc": {}},
    ]})
    config = {"id": afe_id, "mic_num": mics, "agc_enabled": initial, "post_afe_agc_support": support}
    if expected is None:
        with pytest.raises(cv.Invalid):
            schema._final_validate_post_agc(config)
    else:
        assert schema._final_validate_post_agc(config)["post_afe_agc_support"] is expected


def test_quantum_adapter_is_fragment_invariant_and_preserves_failed_quantum(tmp_path):
    source = (AFE / "esp_afe.cpp").read_text()
    methods = ""
    for name in ("reset_post_afe_agc_", "process_post_afe_agc_frame_"):
        start = source.index(("void" if name.startswith("reset") else "bool") + " EspAfe::" + name)
        methods += source[start:source.index("\n}\n", start) + 2] + "\n"
    harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>
constexpr int ESP_AGC_SUCCESS=0;
unsigned calls=0, fail_at=0;
int esp_agc_process(void*,int16_t *in,int16_t *out,int n,int rate) {
 assert(n==160 && rate==16000);++calls;
 if(calls==fail_at)return -1;
 for(int i=0;i<n;++i)out[i]=in[i]*2;
 return 0;
}
struct EspAfe {
 static constexpr size_t kPostAfeAgcQuantumSamples=160;
 void *post_afe_agc_=this;
 int16_t post_afe_agc_input_[160]{},post_afe_agc_output_[160]{};
 size_t post_afe_agc_input_samples_=0;
 void reset_post_afe_agc_();
 bool process_post_afe_agc_frame_(const int16_t*,int16_t*,size_t);
};
'''
    checks = r'''
int main(){
 for(size_t block : {1,7,159,160,257,1024,8192}) for(unsigned failure : {0,3}) {
  EspAfe afe;calls=0;fail_at=failure;afe.reset_post_afe_agc_();
  std::vector<int16_t> input(10000),output;
  for(size_t i=0;i<input.size();++i)input[i]=int16_t((i*37)%1000+1);
  output=input;unsigned failed_frames=0;
  for(size_t pos=0;pos<input.size();pos+=block)
   if(!afe.process_post_afe_agc_frame_(output.data()+pos,output.data()+pos,std::min(block,input.size()-pos)))++failed_frames;
  assert(calls==input.size()/160);assert(failed_frames==(failure ? 1u : 0u));
  for(size_t i=0;i<input.size();++i) {
   if(i<160){assert(output[i]==0);continue;}
   size_t original=i-160;unsigned quantum=original/160+1;
   assert(output[i]==input[original]*(quantum==failure ? 1 : 2));
  }
  afe.reset_post_afe_agc_();int16_t x[160];std::fill(x,x+160,123);
  assert(afe.process_post_afe_agc_frame_(x,x,160));
  for(auto sample:x)assert(sample==0);
  afe.post_afe_agc_=nullptr;int16_t in[]={1,2,3},out[3]{};
  assert(afe.process_post_afe_agc_frame_(in,out,3));assert(std::equal(in,in+3,out));
 }
}
'''
    cpp = tmp_path / "agc.cpp"
    cpp.write_text(harness + methods + checks)
    exe = tmp_path / "agc"
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

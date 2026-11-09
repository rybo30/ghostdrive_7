"""OS / GPU detection and the n_gpu_layers decision.

Hardware probes (platform.*, sysctl, nvidia-smi) are faked so these run the
same on any CI runner.
"""

import pytest

from core import platform_utils as pu


@pytest.fixture
def fake_host(monkeypatch):
    """Configure a fake machine: OS name, CPU arch, sysctl answers, NVIDIA presence."""
    monkeypatch.setattr(pu, "_DEFAULT_GPU_LAYERS", None)

    def configure(system="Darwin", machine="arm64", sysctl=None, nvidia=False):
        values = {"hw.optional.arm64": "1" if machine == "arm64" else None,
                  "machdep.cpu.brand_string": "Apple M3 Pro",
                  "hw.memsize": str(18 * 1024**3)}
        values.update(sysctl or {})
        monkeypatch.setattr(pu.platform, "system", lambda: system)
        monkeypatch.setattr(pu.platform, "machine", lambda: machine)
        monkeypatch.setattr(pu, "_sysctl", lambda name: values.get(name))
        monkeypatch.setattr(pu, "has_nvidia_gpu", lambda: nvidia)

    return configure


@pytest.mark.parametrize("system,expected", [
    ("Darwin", pu.OSType.MACOS),
    ("Windows", pu.OSType.WINDOWS),
    ("Linux", pu.OSType.LINUX),
    ("FreeBSD", pu.OSType.UNSUPPORTED),
])
def test_os_type(monkeypatch, system, expected):
    monkeypatch.setattr(pu.platform, "system", lambda: system)
    assert pu.get_os_type() == expected


def test_apple_silicon_gpu_detected(fake_host):
    fake_host()
    gpu = pu.get_gpu_info()
    assert gpu == {"name": "Apple M3 Pro", "memory_mb": 18 * 1024, "driver_version": "Metal", "backend": "metal"}
    assert pu.get_recommended_gpu_layers() == -1  # all layers on the GPU


def test_apple_silicon_detected_under_rosetta(fake_host):
    # x86_64 Python on an M-series Mac still reports hw.optional.arm64 = 1
    fake_host(machine="x86_64", sysctl={"hw.optional.arm64": "1"})
    assert pu.get_gpu_info()["backend"] == "metal"


def test_intel_mac_has_no_gpu(fake_host):
    fake_host(machine="x86_64")
    assert pu.get_gpu_info() is None
    assert pu.get_recommended_gpu_layers() == 0


def test_small_memory_mac_stays_on_cpu(fake_host):
    fake_host(sysctl={"hw.memsize": str(4 * 1024**3)})
    assert pu.get_recommended_gpu_layers() == 0


def test_linux_without_nvidia_has_no_gpu(fake_host):
    fake_host(system="Linux", machine="x86_64")
    assert pu.get_gpu_info() is None


@pytest.mark.parametrize("vram,layers", [(24576, -1), (12288, 35), (8192, 28), (6144, 20), (4096, 12), (2048, 0)])
def test_nvidia_layers_by_vram(vram, layers):
    assert pu.get_recommended_gpu_layers({"memory_mb": vram, "backend": "cuda"}) == layers


METAL = {"name": "Apple M3 Pro", "memory_mb": 18432, "backend": "metal"}


@pytest.mark.parametrize("configured,supported,expected", [
    (None, True, -1),    # no setting + GPU build -> hardware recommendation
    (None, False, 0),    # CPU-only llama.cpp build -> CPU, whatever the hardware
    (0, True, 0),        # models.yaml n_gpu_layers: 0 forces CPU
    (20, False, 20),     # explicit setting always wins
    ("12", True, 12),    # YAML strings are accepted
    ("bad", True, -1),   # unparseable -> fall back to recommendation
])
def test_resolve_gpu_layers(configured, supported, expected):
    assert pu.resolve_gpu_layers(configured, supported, gpu_info=METAL) == expected


def test_resolve_gpu_layers_probes_hardware_once(fake_host, monkeypatch):
    fake_host()
    calls = []
    real = pu.get_recommended_gpu_layers
    monkeypatch.setattr(pu, "get_recommended_gpu_layers", lambda *a: calls.append(1) or real(*a))
    assert pu.resolve_gpu_layers(None, True) == -1
    assert pu.resolve_gpu_layers(None, True) == -1
    assert len(calls) == 1

from __future__ import annotations

import pytest
from PIL import Image

from eink_display.display.waveshare import (
    FULL_REFRESH_INTERVAL,
    MAX_PARTIAL_REGIONS,
    MockEPDDriver,
    WaveshareEPDDriver,
)


class _FakeEPD:
    def __init__(self) -> None:
        self.width = 800
        self.height = 480
        self.init_calls = 0
        self.clear_calls = 0
        self.display_calls: list[bytes] = []
        self.partial_calls: list[tuple[bytes, int, int, int, int]] = []
        self.getbuffer_calls = []
        self.sleep_calls = 0

    def init(self) -> None:
        self.init_calls += 1

    def Clear(self) -> None:
        self.clear_calls += 1

    def display(self, buffer: bytes) -> None:
        self.display_calls.append(bytes(buffer))

    def display_Partial(
        self, buffer: bytes, xstart: int, ystart: int, xend: int, yend: int
    ) -> None:
        self.partial_calls.append((bytes(buffer), xstart, ystart, xend, yend))

    def getbuffer(self, image: Image.Image) -> bytes:
        self.getbuffer_calls.append(image.copy())
        return image.tobytes()

    def sleep(self) -> None:
        self.sleep_calls += 1


class TestWaveshareEPDDriver:
    def test_initialize_and_display_flow(self) -> None:
        fake = _FakeEPD()
        driver = WaveshareEPDDriver(epd=fake)

        driver.initialize()
        assert fake.init_calls == 1

        driver.clear()
        assert fake.clear_calls == 1

        image = Image.new("1", (800, 480), 0)
        driver.display_image(image)

        assert len(fake.getbuffer_calls) == 1
        assert fake.display_calls == [image.tobytes()]
        assert not fake.partial_calls

        driver.sleep()
        assert fake.sleep_calls == 1

    def test_requires_initialization(self) -> None:
        fake = _FakeEPD()
        driver = WaveshareEPDDriver(epd=fake)

        with pytest.raises(RuntimeError):
            driver.clear()

        driver.initialize()
        driver.clear()

    def test_updates_use_previous_frame_data(self) -> None:
        fake = _FakeEPD()
        driver = WaveshareEPDDriver(epd=fake)
        driver.initialize()

        base = Image.new("1", (800, 480), 255)
        driver.display_image(base)
        assert fake.display_calls[-1] == base.tobytes()

        updated = base.copy()
        updated.putpixel((0, 0), 0)
        driver.display_image(updated)

        assert len(fake.partial_calls) == 1
        _, xstart, ystart, xend, yend = fake.partial_calls[0]
        assert (xstart, ystart) == (0, 0)
        assert xend > xstart and yend > ystart

    def test_skips_refresh_when_frame_identical(self) -> None:
        fake = _FakeEPD()
        driver = WaveshareEPDDriver(epd=fake)
        driver.initialize()

        base = Image.new("1", (800, 480), 255)
        driver.display_image(base)
        partial_count = len(fake.partial_calls)

        driver.display_image(base.copy())
        assert len(fake.partial_calls) == partial_count

    def test_periodic_full_refresh_after_threshold(self) -> None:
        fake = _FakeEPD()
        driver = WaveshareEPDDriver(epd=fake)
        driver.initialize()

        base = Image.new("1", (800, 480), 255)
        driver.display_image(base)
        assert fake.display_calls == [base.tobytes()]

        for i in range(FULL_REFRESH_INTERVAL + 1):
            updated = base.copy()
            updated.putpixel((i % base.width, (i // base.width) + 1), 0)
            driver.display_image(updated)

        assert len(fake.display_calls) >= 2

    def test_partial_updates_split_disjoint_regions(self) -> None:
        fake = _FakeEPD()
        driver = WaveshareEPDDriver(epd=fake)
        driver.initialize()

        base = Image.new("1", (800, 480), 255)
        driver.display_image(base)

        updated = base.copy()
        updated.putpixel((5, 5), 0)
        updated.putpixel((750, 430), 0)
        driver.display_image(updated)

        assert len(fake.partial_calls) == 2
        widths = [xend - xstart for _, xstart, _, xend, _ in fake.partial_calls]
        assert all(width < 400 for width in widths)

    def test_partial_updates_fall_back_when_exceeding_limit(self) -> None:
        fake = _FakeEPD()
        driver = WaveshareEPDDriver(epd=fake)
        driver.initialize()

        base = Image.new("1", (800, 480), 255)
        driver.display_image(base)

        updated = base.copy()
        for idx in range(MAX_PARTIAL_REGIONS + 3):
            x = (idx * 70) % base.width
            y = (idx * 50) % base.height
            updated.putpixel((x, y), 0)

        driver.display_image(updated)
        assert len(fake.partial_calls) == 1


class TestMockEPDDriver:
    @staticmethod
    def test_mock_records_frames_and_saves(tmp_path) -> None:
        driver = MockEPDDriver(output_dir=tmp_path)
        driver.initialize()
        driver.clear()

        frame = Image.new("1", driver.resolution, 0)
        driver.display_image(frame)

        history = driver.history
        assert len(history) == 2  # clear() adds a blank frame, then display_image
        assert history[-1].tobytes() == frame.tobytes()

        saved_files = list(tmp_path.glob("mock-frame-*.png"))
        assert len(saved_files) == 1

    @staticmethod
    def test_mock_requires_initialization() -> None:
        driver = MockEPDDriver()

        with pytest.raises(RuntimeError):
            driver.display_image(Image.new("1", driver.resolution, 0))

        driver.initialize()
        driver.display_image(Image.new("1", driver.resolution, 0))

    @staticmethod
    def test_mock_validates_resolution() -> None:
        driver = MockEPDDriver()
        driver.initialize()

        with pytest.raises(ValueError):
            driver.display_image(Image.new("1", (100, 100), 0))

import numpy as np

from colorroi_analyzer.analysis import analyze_image
from colorroi_analyzer.core import auto_hair_mask, fill_roi_from_boundary, load_rgb_image


def test_fill_roi_from_closed_boundary():
    boundary = np.zeros((120, 160), dtype=bool)
    boundary[30:90, 40] = True
    boundary[30:90, 120] = True
    boundary[30, 40:121] = True
    boundary[90, 40:121] = True

    roi = fill_roi_from_boundary(boundary)

    assert roi.sum() > 3000
    assert roi[60, 80]
    assert not roi[10, 10]


def test_analyze_sample_image_smoke():
    img = load_rgb_image("0.jpg")
    h, w = img.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    center_y, center_x = h / 2, w / 2
    ellipse = ((xx - center_x) ** 2 / (w * 0.28) ** 2 + (yy - center_y) ** 2 / (h * 0.28) ** 2) <= 1
    boundary = ellipse ^ np.logical_and(
        ((xx - center_x) ** 2 / (w * 0.25) ** 2 + (yy - center_y) ** 2 / (h * 0.25) ** 2) <= 1,
        ellipse,
    )
    hair = (np.abs(xx - center_x) < 3) & (yy > h * 0.35) & (yy < h * 0.65)

    result = analyze_image(img, boundary, hair)

    assert result.roi_px > 50
    assert result.hair_px > 0
    assert np.isfinite(result.clusters.dmdi)
    assert abs(sum(result.clusters.ratios.values()) - 1) < 1e-6


def test_auto_hair_mask_shape_and_type():
    img = load_rgb_image("0.jpg")

    hair = auto_hair_mask(img)

    assert hair.shape == img.shape[:2]
    assert hair.dtype == bool


def test_analyze_uses_auto_hair_when_manual_mask_empty():
    img = load_rgb_image("0.jpg")
    h, w = img.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    center_y, center_x = h / 2, w / 2
    ellipse = ((xx - center_x) ** 2 / (w * 0.28) ** 2 + (yy - center_y) ** 2 / (h * 0.28) ** 2) <= 1
    boundary = ellipse ^ np.logical_and(
        ((xx - center_x) ** 2 / (w * 0.25) ** 2 + (yy - center_y) ** 2 / (h * 0.25) ** 2) <= 1,
        ellipse,
    )

    result = analyze_image(img, boundary, np.zeros((h, w), dtype=bool))

    assert result.roi_px > 50
    assert result.effective_px <= result.roi_px
    assert result.hair_px >= 0
    assert result.hair_source == "auto"


def test_analyze_preserves_auto_hair_source_hint():
    img = load_rgb_image("0.jpg")
    h, w = img.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    center_y, center_x = h / 2, w / 2
    ellipse = ((xx - center_x) ** 2 / (w * 0.28) ** 2 + (yy - center_y) ** 2 / (h * 0.28) ** 2) <= 1
    boundary = ellipse ^ np.logical_and(
        ((xx - center_x) ** 2 / (w * 0.25) ** 2 + (yy - center_y) ** 2 / (h * 0.25) ** 2) <= 1,
        ellipse,
    )
    hair = (np.abs(xx - center_x) < 3) & (yy > h * 0.35) & (yy < h * 0.65)

    result = analyze_image(img, boundary, hair, hair_source_hint="auto")

    assert result.hair_px > 0
    assert result.hair_source == "auto"

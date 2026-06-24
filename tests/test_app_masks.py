import numpy as np

from app import _extract_masks
from colorroi_analyzer.core import fill_roi_from_boundary


def test_extract_masks_prefers_canvas_json_paths():
    json_data = {
        "objects": [
            {
                "type": "path",
                "stroke": "rgba(255,220,0,1)",
                "strokeWidth": 8,
                "path": [
                    ["M", 30, 30],
                    ["L", 130, 30],
                    ["L", 130, 100],
                    ["L", 30, 100],
                    ["L", 30, 30],
                ],
            },
            {
                "type": "path",
                "stroke": "rgba(230,45,24,1)",
                "strokeWidth": 6,
                "path": [
                    ["M", 70, 50],
                    ["L", 95, 75],
                ],
            },
        ]
    }

    # image_data 故意传全 0，确保测试覆盖的是 JSON 路径解析，而不是截图颜色识别。
    image_data = np.zeros((120, 160, 4), dtype=np.uint8)
    roi_boundary, hair_mask = _extract_masks(
        image_data=image_data,
        json_data=json_data,
        target_shape=(120, 160),
        display_shape=(120, 160),
        scale=1.0,
    )

    roi = fill_roi_from_boundary(roi_boundary)

    assert roi_boundary.sum() > 1000
    assert hair_mask.sum() > 100
    assert roi.sum() > 4000
    assert roi[60, 80]


def test_extract_masks_applies_eraser_paths_in_draw_order():
    json_data = {
        "objects": [
            {
                "type": "path",
                "stroke": "rgba(255,220,0,1)",
                "strokeWidth": 10,
                "path": [["M", 20, 40], ["L", 140, 40]],
            },
            {
                "type": "path",
                "stroke": "rgba(230,45,24,1)",
                "strokeWidth": 10,
                "path": [["M", 20, 70], ["L", 140, 70]],
            },
            {
                "type": "path",
                "stroke": "rgba(255,255,255,1)",
                "strokeWidth": 16,
                "path": [["M", 78, 20], ["L", 78, 90]],
            },
        ]
    }

    image_data = np.zeros((100, 160, 4), dtype=np.uint8)
    roi_boundary, hair_mask = _extract_masks(
        image_data=image_data,
        json_data=json_data,
        target_shape=(100, 160),
        display_shape=(100, 160),
        scale=1.0,
    )

    # 白色橡皮擦笔画应只擦除穿过的局部，而不是把整条 ROI 或毛发对象删除。
    assert not roi_boundary[40, 78]
    assert not hair_mask[70, 78]
    assert roi_boundary[40, 35]
    assert roi_boundary[40, 120]
    assert hair_mask[70, 35]
    assert hair_mask[70, 120]

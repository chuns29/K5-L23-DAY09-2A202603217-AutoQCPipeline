"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line


def fix(ds, issues, cfg):
    errors = [issue for issue in issues if issue.severity == ERROR]
    fixes = []

    def record(image, line, action, before, after):
        fixes.append(dict(image=image, line=line, action=action, before=before, after=after))

    # Xoá ảnh trước: mọi lỗi dòng của ảnh bị loại đều không cần xử lý nữa.
    removed = {i.image for i in errors
               if i.code.startswith("DUP_IMAGE_") or i.code in {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}}
    for stem in sorted(removed):
        paths = [p for p in ds.image_files() if p.stem == stem]
        label_path = ds.label_path(stem)
        if label_path.exists():
            paths.append(label_path)
        if paths:
            before = ", ".join(str(p.relative_to(ds.root)) for p in paths)
            for path in paths:
                path.unlink()
            record(stem, "", "remove_image", before, "")

    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        before = ds.yaml_path.read_text(encoding="utf-8") if ds.yaml_path.exists() else ""
        data = yaml.safe_load(before) or {}
        expected_names = dict(enumerate(cfg["classes"]))
        if data.get("names") != expected_names:
            data["names"] = expected_names
            after = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
            ds.yaml_path.write_text(after, encoding="utf-8")
            record("data.yaml", "", "rename_classes", before, after)

    missing = sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"} - removed)
    for stem in missing:
        if not ds.label_path(stem).exists():
            record(stem, "", "needs_label", "(không có file)", "chuyển người gán")

    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    line_errors = defaultdict(lambda: defaultdict(set))
    for issue in errors:
        if (issue.image not in removed and issue.line is not None
                and issue.code in drop_codes | {"BOX_OUT_OF_IMAGE"}):
            line_errors[issue.image][issue.line].add(issue.code)

    for stem, codes_by_line in sorted(line_errors.items()):
        path = ds.label_path(stem)
        if not path.exists():
            continue
        # Duyệt bản gốc một lần để xoá dòng không làm lệch số dòng kế tiếp.
        original = path.read_text(encoding="utf-8").splitlines(keepends=True)
        updated = []
        changed = False
        for no, raw_line in enumerate(original, 1):
            codes = codes_by_line.get(no, set())
            before = raw_line.rstrip("\r\n")
            if codes & drop_codes:
                record(stem, no, "drop_line", before, "")
                changed = True
                continue
            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    c, x, y, w, h = parse_yolo_line(before)
                except (ValueError, OverflowError):
                    record(stem, no, "drop_line", before, "")
                    changed = True
                    continue
                left, right = max(0.0, x - w / 2), min(1.0, x + w / 2)
                top, bottom = max(0.0, y - h / 2), min(1.0, y + h / 2)
                if right <= left or bottom <= top:
                    record(stem, no, "drop_line", before, "")
                    changed = True
                    continue
                if left != x - w / 2 or right != x + w / 2 or top != y - h / 2 or bottom != y + h / 2:
                    clipped = ((left + right) / 2, (top + bottom) / 2, right - left, bottom - top)
                    after = f"{c} " + " ".join(f"{v:.12g}" for v in clipped)
                    record(stem, no, "clip_box", before, after)
                    raw_line = after + ("\n" if raw_line.endswith("\n") else "")
                    changed = True
            updated.append(raw_line)
        if changed:
            path.write_text("".join(updated), encoding="utf-8")
    return fixes

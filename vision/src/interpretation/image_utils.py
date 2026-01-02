# src/interpretation/image_utils.py

def crop_from_center(img, cx, cy, w, h):
    x1 = max(int(cx - w // 2), 0)
    y1 = max(int(cy - h // 2), 0)
    x2 = min(int(cx + w // 2), img.shape[1])
    y2 = min(int(cy + h // 2), img.shape[0])
    return img[y1:y2, x1:x2]

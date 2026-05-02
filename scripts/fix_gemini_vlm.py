"""
Apply all fixes to the ScreenAwareTaskAgent project.
Run from:  E:\sliit-project\ScreenAwareTaskAgent
"""
import os

BASE = r'E:\sliit-project\ScreenAwareTaskAgent'


def fix_file(path, old_bytes, new_bytes, label):
    with open(path, 'rb') as f:
        content = f.read()
    if old_bytes in content:
        content = content.replace(old_bytes, new_bytes, 1)
        with open(path, 'wb') as f:
            f.write(content)
        print(f"  [OK] {label}")
        return True
    else:
        print(f"  [MISS] {label} — pattern not found")
        return False


# =============================================================================
# 1. gemini_vlm.py — Fix 1: Strengthen system prompt
# =============================================================================
gemini_path = os.path.join(BASE, r'vision\src\vision\vlm\gemini_vlm.py')
print("Fixing gemini_vlm.py...")

old_prompt = (
    b'"The input image is already a crop of the visible screen. Detect every visible UI element inside that crop. "\r\n'
    b'            "including buttons, inputs, links, tabs, menus, checkboxes, radios, dropdowns, toggles, "\r\n'
    b'            "panes, taskbar items, toolbar controls, browser chrome, window chrome, sidebar entries, "\r\n'
    b'            "headings, labels, icons, status bars, and meaningful text. "\r\n'
    b'            "Prefer high recall over minimalism. If the screen is complex, return many small elements. "\r\n'
    b'            "Do not collapse the whole screen into only a few detections. "\r\n'
    b'            "Return this exact root shape with required fields: "\r\n'
    b'            "{image, image_size, coordinate_system, element_count, elements}. "\r\n'
    b'            "coordinate_system must be \'pixel\'. "\r\n'
    b'            "All element coordinates must be relative to the crop/screen, not the full camera frame. "\r\n'
    b'            "You may return bounding boxes either as absolute pixel coordinates (integers) or as normalized fractions in [0,1]. "\r\n'
    b'            "If using normalized fractions, they are relative to the crop width/height. "\r\n'
    b'            "elements must be an array of objects with fields: "\r\n'
    b'            "id, type, label, description, state, dx, dy, confidence, source, bbox. "\r\n'
    b'            "confidence must be numeric in [0,1]. "\r\n'
    b'            "bbox must be a tight pixel box [x_min, y_min, x_max, y_max] around the element, "\r\n'
    b'            "using screen-local pixels, or a normalized [x_min, y_min, x_max, y_max] in [0,1]. "\r\n'
)
new_prompt = (
    b'"The input image is the CROPPED screen region -- its top-left pixel is coordinate (0, 0). "\r\n'
    b'            "Detect every visible UI element inside this crop: buttons, inputs, links, tabs, menus, "\r\n'
    b'            "checkboxes, radios, dropdowns, toggles, panes, taskbar items, toolbar controls, browser chrome, "\r\n'
    b'            "window chrome, sidebar entries, headings, labels, icons, status bars, and meaningful text. "\r\n'
    b'            "Prefer high recall over minimalism. If the screen is complex, return many small elements. "\r\n'
    b'            "Do not collapse the whole screen into only a few detections. "\r\n'
    b'            "Return this exact root shape with required fields: "\r\n'
    b'            "{image, image_size, coordinate_system, element_count, elements}. "\r\n'
    b'            "coordinate_system must be \'pixel\'. "\r\n'
    b'            "CRITICAL: ALL dx, dy, bbox coordinates MUST be relative to the TOP-LEFT of THIS CROP (0, 0). "\r\n'
    b'            "Do NOT use absolute camera-frame coordinates -- the crop already starts at (0, 0). "\r\n'
    b'            "You may use absolute pixel integers OR normalized fractions in [0,1] relative to this crop. "\r\n'
    b'            "elements must be an array of objects with fields: "\r\n'
    b'            "id, type, label, description, state, dx, dy, confidence, source, bbox. "\r\n'
    b'            "confidence must be numeric in [0,1]. "\r\n'
    b'            "bbox must be [x_min, y_min, x_max, y_max] tightly around the element in crop-local coordinates. "\r\n'
    b'            "Normalized fractions in [0,1] are relative to this crop width/height. "\r\n'
)
fix_file(gemini_path, old_prompt, new_prompt, "gemini_vlm: system_prompt strengthened")

# Fix 2: Fix _analyze_region NameError
old_region = (
    b'        normalized["elements"] = self._refine_elements_with_image(\r\n'
    b'            list(normalized.get("elements", [])),\r\n'
    b'            screen_crop,\r\n'
    b'            origin_x=screen_x1,\r\n'
    b'            origin_y=screen_y1,\r\n'
    b'            frame_width=image_width,\r\n'
    b'            frame_height=image_height,\r\n'
    b'        )\r\n'
    b'\r\n'
    b'        return list(normalized.get("elements", []))\r\n'
)
new_region = (
    b'        # Refine bboxes against the region crop (local variable `crop`).\r\n'
    b'        # Use x1/y1 as origin offsets into the full frame.\r\n'
    b'        normalized["elements"] = self._refine_elements_with_image(\r\n'
    b'            list(normalized.get("elements", [])),\r\n'
    b'            crop,\r\n'
    b'            origin_x=x1,\r\n'
    b'            origin_y=y1,\r\n'
    b'            frame_width=image_width,\r\n'
    b'            frame_height=image_height,\r\n'
    b'        )\r\n'
    b'\r\n'
    b'        return list(normalized.get("elements", []))\r\n'
)
fix_file(gemini_path, old_region, new_region, "gemini_vlm: _analyze_region NameError fixed")


# =============================================================================
# 2. vision/src/api.py — Remove duplicate _finalize_elements_with_dxdy call
# =============================================================================
api_path = os.path.join(BASE, r'vision\src\api.py')
print("\nFixing vision/src/api.py...")

old_dupe = (
    b'        payload = _finalize_elements_with_dxdy(payload, image.shape[1], image.shape[0])\r\n'
    b'        final_payload = _strip_internal_fields(payload)\r\n'
    b'        with open(final_json_path, "w", encoding="utf-8") as f:\r\n'
    b'            json.dump(final_payload, f, indent=2)\r\n'
    b'\r\n'
    b'        return {\r\n'
)
new_dupe = (
    b'        # NOTE: _finalize_elements_with_dxdy already called above; do not call again.\r\n'
    b'        return {\r\n'
)
fix_file(api_path, old_dupe, new_dupe, "api.py: duplicate _finalize_elements_with_dxdy removed")


# =============================================================================
# 3. backend/core/agentic_loop_v2.py — Multi-fix:
#    a) Add coordinate remapper (frame_dx/dy -> dx/dy for LLM)
#    b) Fix needs_input infinite loop guard
#    c) Remove dead logger.info after return
# =============================================================================
loop_path = os.path.join(BASE, r'backend\core\agentic_loop_v2.py')
print("\nFixing backend/core/agentic_loop_v2.py...")

# Fix 3a: Add _remap_to_absolute_coords helper and invoke before LLM calls
# Insert helper after VISION_BASE_URL/LLM_BASE_URL/HID_API_URL definitions
old_urls = (
    b'VISION_BASE_URL = "http://localhost:8001"\r\n'
    b'LLM_BASE_URL = "http://localhost:8002"\r\n'
    b'HID_API_URL = "http://localhost:3015/hid/command"\r\n'
)
new_urls = (
    b'VISION_BASE_URL = "http://localhost:8001"\r\n'
    b'LLM_BASE_URL = "http://localhost:8002"\r\n'
    b'HID_API_URL = "http://localhost:3015/hid/command"\r\n'
    b'\r\n'
    b'\r\n'
    b'def _remap_to_absolute_coords(screen_data: dict) -> dict:\r\n'
    b'    """\r\n'
    b'    Remap each element\'s dx/dy to use absolute webcam-frame coordinates\r\n'
    b'    (frame_dx / frame_dy) instead of screen-relative coordinates.\r\n'
    b'\r\n'
    b'    The vision pipeline produces both:\r\n'
    b'      dx/dy       -- screen-relative (offset from cropped screen top-left)\r\n'
    b'      frame_dx/dy -- absolute (offset from full webcam frame top-left)\r\n'
    b'\r\n'
    b'    The LLM uses dx/dy values to generate HID mouse_move commands, so we must\r\n'
    b'    replace dx/dy with frame_dx/dy before sending vision data to the LLM so\r\n'
    b'    that generated coordinates are correct for the physical HID device.\r\n'
    b'    """\r\n'
    b'    if not isinstance(screen_data, dict):\r\n'
    b'        return screen_data\r\n'
    b'\r\n'
    b'    # Handle common vision response wrappers\r\n'
    b'    for wrapper_key in ("vision_data", "vision_output", "vision"):\r\n'
    b'        if wrapper_key in screen_data and isinstance(screen_data[wrapper_key], dict):\r\n'
    b'            inner = screen_data[wrapper_key]\r\n'
    b'            remapped = dict(screen_data)\r\n'
    b'            remapped[wrapper_key] = _remap_elements(inner)\r\n'
    b'            return remapped\r\n'
    b'\r\n'
    b'    return _remap_elements(screen_data)\r\n'
    b'\r\n'
    b'\r\n'
    b'def _remap_elements(payload: dict) -> dict:\r\n'
    b'    """Replace dx/dy with frame_dx/frame_dy values if they exist."""\r\n'
    b'    elements = payload.get("elements")\r\n'
    b'    if not isinstance(elements, list) or not elements:\r\n'
    b'        return payload\r\n'
    b'\r\n'
    b'    remapped_elements = []\r\n'
    b'    for elem in elements:\r\n'
    b'        if not isinstance(elem, dict):\r\n'
    b'            remapped_elements.append(elem)\r\n'
    b'            continue\r\n'
    b'        new_elem = dict(elem)\r\n'
    b'        frame_dx = elem.get("frame_dx")\r\n'
    b'        frame_dy = elem.get("frame_dy")\r\n'
    b'        if frame_dx is not None:\r\n'
    b'            try:\r\n'
    b'                new_elem["dx"] = int(round(float(frame_dx)))\r\n'
    b'            except Exception:\r\n'
    b'                pass\r\n'
    b'        if frame_dy is not None:\r\n'
    b'            try:\r\n'
    b'                new_elem["dy"] = int(round(float(frame_dy)))\r\n'
    b'            except Exception:\r\n'
    b'                pass\r\n'
    b'        remapped_elements.append(new_elem)\r\n'
    b'\r\n'
    b'    result = dict(payload)\r\n'
    b'    result["elements"] = remapped_elements\r\n'
    b'    return result\r\n'
)
fix_file(loop_path, old_urls, new_urls, "agentic_loop_v2: added _remap_to_absolute_coords helper")

# Fix 3b: Wrap _plan_todo_list call with remapper
old_todo = (
    b'        try:\r\n'
    b'            todo_result = await _plan_todo_list(initial_screen, user_task)\r\n'
    b'        except Exception as exc:\r\n'
)
new_todo = (
    b'        try:\r\n'
    b'            todo_result = await _plan_todo_list(_remap_to_absolute_coords(initial_screen), user_task)\r\n'
    b'        except Exception as exc:\r\n'
)
fix_file(loop_path, old_todo, new_todo, "agentic_loop_v2: remap coords before plan_todo_list")

# Fix 3c: Wrap _plan_step_hid call with remapper (current_screen)
old_step_hid = (
    b'                    hid_result = await _plan_step_hid(\r\n'
    b'                        current_screen, todo_list, step, user_task\r\n'
    b'                    )\r\n'
)
new_step_hid = (
    b'                    hid_result = await _plan_step_hid(\r\n'
    b'                        _remap_to_absolute_coords(current_screen), todo_list, step, user_task\r\n'
    b'                    )\r\n'
)
fix_file(loop_path, old_step_hid, new_step_hid, "agentic_loop_v2: remap coords before plan_step_hid")

# Fix 3d: Wrap _evaluate_step call with remapper (new_screen)
old_eval = (
    b'                    evaluation = await _evaluate_step(\r\n'
    b'                        new_screen, step, user_task, todo_list\r\n'
    b'                    )\r\n'
)
new_eval = (
    b'                    evaluation = await _evaluate_step(\r\n'
    b'                        _remap_to_absolute_coords(new_screen), step, user_task, todo_list\r\n'
    b'                    )\r\n'
)
fix_file(loop_path, old_eval, new_eval, "agentic_loop_v2: remap coords before evaluate_step")

# Fix 3e: needs_input infinite loop guard — add counter and increment attempt
old_needs_input = (
    b'                    await emit(\r\n'
    b'                        {\"type\": \"input_received\", \"step_index\": step_index, \"field\": field}\r\n'
    b'                    )\r\n'
    b'                    # Do NOT increment attempt \xe2\x80\x94 retry with the enriched context\r\n'
)
new_needs_input = (
    b'                    await emit(\r\n'
    b'                        {\"type\": \"input_received\", \"step_index\": step_index, \"field\": field}\r\n'
    b'                    )\r\n'
    b'                    # Increment attempt so needs_input cannot loop indefinitely\r\n'
    b'                    attempt += 1\r\n'
)
fix_file(loop_path, old_needs_input, new_needs_input, "agentic_loop_v2: needs_input loop guard (increment attempt)")

# Fix 3f: Remove dead logger.info after return in _normalize_perception
old_dead = (
    b'        # Fallback: return original object so nothing is lost\r\n'
    b'        return screen_data\r\n'
    b'\r\n'
    b'        logger.info("AgentRunRecorder: run dir \xe2\x86\x92 %s", self.run_dir)\r\n'
)
new_dead = (
    b'        # Fallback: return original object so nothing is lost\r\n'
    b'        return screen_data\r\n'
)
fix_file(loop_path, old_dead, new_dead, "agentic_loop_v2: removed dead logger.info after return")


# =============================================================================
# 4. perception_pipeline.py — Remove duplicate unreachable main() code
# =============================================================================
pp_path = os.path.join(BASE, r'vision\src\perception_pipeline.py')
print("\nFixing vision/src/perception_pipeline.py...")

old_dupe_main = (
    b'    print("ERROR: Provide either --image or --image-dir")\r\n'
    b'    sys.exit(1)\r\n'
    b'    parser.add_argument("--image", help="Path to image")\r\n'
    b'    parser.add_argument("--image-dir", help="Directory of images for batch processing")\r\n'
)
new_dupe_main = (
    b'    print("ERROR: Provide either --image or --image-dir")\r\n'
    b'    sys.exit(1)\r\n'
    b'# Note: code below this point was unreachable (after sys.exit) and has been removed.\r\n'
)
# For perception_pipeline.py we truncate at the second sys.exit(1)
with open(pp_path, 'rb') as f:
    pp_content = f.read()
# Find first sys.exit(1) after "Provide either"
marker = b'    print("ERROR: Provide either --image or --image-dir")\r\n    sys.exit(1)\r\n'
first = pp_content.find(marker)
second = pp_content.find(marker, first + 1)
if second >= 0:
    pp_content = pp_content[:second] + b'    print("ERROR: Provide either --image or --image-dir")\r\n    sys.exit(1)\r\n'
    with open(pp_path, 'wb') as f:
        f.write(pp_content)
    print("  [OK] perception_pipeline.py: duplicate main() code removed")
else:
    print("  [SKIP] perception_pipeline.py: second sys.exit(1) not found (may already be clean)")

print("\nAll fixes complete.")

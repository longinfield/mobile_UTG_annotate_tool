import openai
import os
from GPT_model import *
from flask import Flask, render_template
import os, json, base64, mimetypes
from io import BytesIO
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

"""
目录结构（目标文件夹）期望：
<target_dir>/
  ├─ utg.json                      # UI 跳转图（数组的数组）
  ├─ indexList.json                # visitList
  ├─ <i>_Leaf.json                 # 每个节点的leaf（若存在）
  ├─ <i>_VH.json                   # 每个节点的vh（若存在）
  └─ <i>_screenshot.jpg            # 每个节点截图

后端会另外在该目录维护：
  └─ positions.json                # { "<label>": {"x": float, "y": float}, ... }
  └─ state_lock.json               # 记录当前由后端管理的文件版本（可选）
"""

app = Flask(__name__)
CORS(app)

configs = load_config()
text_model = TextModel(model=configs["OPENAI_API_MODEL"], temperature=configs["TEMPERATURE"], max_tokens=configs["MAX_TOKENS"])

CONFIG_PATH = os.path.join(os.getcwd(), "server_config.json")
TARGET_KEY = "target_dir"

# ===== helper: id 规范化 =====
def _norm_id(nid):
    """接受 '12' / '12_screenshot.jpg' / int；返回 int 索引和标准文件名前缀 '12'"""
    if isinstance(nid, int):
        i = nid
    else:
        s = str(nid).strip()
        if s.endswith("_screenshot.jpg"):
            s = s.replace("_screenshot.jpg", "")
        i = int(s)
    return i, str(i)

def _bbox_similar(a, b, thr=10):
    """与前端一致的近似判断：文本相等 + 4 边界差值均 < thr"""
    if a.get("text") != b.get("text"):
        return False
    return (
        abs(a.get("boundLeft", 0)   - b.get("boundLeft", 0))   < thr and
        abs(a.get("boundTop", 0)    - b.get("boundTop", 0))    < thr and
        abs(a.get("boundRight", 0)  - b.get("boundRight", 0))  < thr and
        abs(a.get("boundBottom", 0) - b.get("boundBottom", 0)) < thr
    )

def _merge_bbox_lists(lists, thr=10):
    """把多个 Leaf 列表按 bbox 相似性合并；返回 merged, remap_list
    remap_list[i][orig_idx] -> merged_idx，用于可选的反向映射（若前端需要）
    """
    merged = []
    remaps = []
    for leaf in lists:
        mapping = {}
        for idx, elem in enumerate(leaf):
            found = -1
            for j, ex in enumerate(merged):
                if _bbox_similar(ex, elem, thr=thr):
                    found = j; break
            if found == -1:
                merged.append(elem)
                found = len(merged) - 1
            mapping[idx] = found
        remaps.append(mapping)
    return merged, remaps

def _safe_list(obj, length_min=0):
    return obj if isinstance(obj, list) else ([] if length_min == 0 else [])[0:0]

def _dedupe(seq):
    seen = set(); out = []
    for x in seq:
        if isinstance(x, dict):
            # 为边做去重：用 (element, screen) 作为键
            key = (x.get("element"), x.get("screen"))
        else:
            key = x
        if key in seen:
            continue
        seen.add(key); out.append(x)
    return out

@app.post("/api/merge")
def merge_nodes_api():
    """
    合并节点（在后端进行计算并落盘）
    接收 JSON：
    {
      "keep": <int | "12" | "12_screenshot.jpg">,      # 保留节点
      "remove": [<int|"..">, ...],                     # 被合并节点（>=1）
      "bbox_threshold": 10,                            # 可选，默认10
      "dry_run": false                                 # 可选，true时只返回不落盘
    }

    返回：
    {
      "ok": true,
      "changes": {
        "utg_out_changed": [idx...],       # 哪些源索引的出边被改
        "utg_in_changed": [idx...],        # 哪些源索引因入边重定向而改
        "leaf_written": ["12_Leaf.json", ...],
        "vh_written":   ["12_VH.json", ...],
        "removed_leaf": ["13_Leaf.json", ...],
        "removed_vh":   ["13_VH.json", ...],
        "positions_removed": ["13_screenshot.jpg", ...],
        "indexList_changed": true|false
      },
      "result_summary": {
        "keep": 12,
        "removed": [13, 15],
        "keep_leaf_count":  XX,
        "keep_vh_keys":     YY
      }
    }
    """
    target = get_target_dir()
    if not target or not os.path.isdir(target):
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400

    data = request.get_json(force=True) or {}
    if "keep" not in data or "remove" not in data:
        return jsonify({"ok": False, "error": "Missing 'keep' or 'remove'"}), 400

    thr = int(data.get("bbox_threshold", 10))
    dry_run = bool(data.get("dry_run", False))

    keep_i, keep_prefix = _norm_id(data["keep"])
    remove_ids = data["remove"]
    remove_norm = []
    for nid in remove_ids:
        ri, rp = _norm_id(nid)
        if ri == keep_i:
            continue
        remove_norm.append((ri, rp))
    if not remove_norm:
        return jsonify({"ok": False, "error": "Nothing to merge"}), 400
    removed_indices = sorted(set([ri for ri, _ in remove_norm]))

    # 读取文件
    utg = load_json(os.path.join(target, "utg.json"), default=[])
    visit_list = load_json(os.path.join(target, "indexList.json"), default=[])
    positions = load_json(os.path.join(target, "positions.json"), default={})

    # --- 1) 合并 Leaf ---
    leaf_paths = []
    leaf_lists = []
    keep_leaf_path = os.path.join(target, f"{keep_prefix}_Leaf.json")
    if os.path.exists(keep_leaf_path):
        leaf_lists.append(load_json(keep_leaf_path, default=[]))
        leaf_paths.append(keep_leaf_path)
    for ri, rp in remove_norm:
        p = os.path.join(target, f"{rp}_Leaf.json")
        if os.path.exists(p):
            leaf_lists.append(load_json(p, default=[]))
            leaf_paths.append(p)

    merged_leaf, _remaps = _merge_bbox_lists(leaf_lists, thr=thr) if leaf_lists else ([], [])

    # --- 2) 合并 VH（策略：浅层合并，后写入 keep；冲突键后者覆盖前者，可按需改成更细策略） ---
    keep_vh = {}
    keep_vh_path = os.path.join(target, f"{keep_prefix}_VH.json")
    if os.path.exists(keep_vh_path):
        keep_vh = load_json(keep_vh_path, default={})

    removed_vh_paths = []
    for ri, rp in remove_norm:
        p = os.path.join(target, f"{rp}_VH.json")
        if os.path.exists(p):
            v = load_json(p, default={})
            if isinstance(v, dict):
                keep_vh.update(v)   # 简单覆盖合并
            removed_vh_paths.append(p)

    # --- 3) 合并出边（keep 出边 = keep 出边 ∪ 每个 removed 的出边），并去重/去 self-loop ---
    def _get_out(i):
        return utg[i] if i < len(utg) and isinstance(utg[i], list) else []
    keep_out = list(_get_out(keep_i))
    for ri in removed_indices:
        for e in _get_out(ri):
            tgt = int(e.get("screen"))
            if tgt == keep_i:   # 避免自环
                continue
            keep_out.append({"element": int(e.get("element")), "screen": tgt})
    keep_out = _dedupe([x for x in keep_out if x.get("screen") != keep_i])

    # --- 4) 重定向入边（所有指向 removed 的边 -> 指向 keep），并去重/去自环 ---
    in_changed = set()
    out_changed = set()
    for src in range(len(utg)):
        lst = _get_out(src)
        if not lst:
            continue
        changed = False
        new_lst = []
        for e in lst:
            tgt = int(e.get("screen"))
            if tgt in removed_indices:
                changed = True
                in_changed.add(src)
                # 指向 keep
                if keep_i != src:   # 避免自环
                    new_lst.append({"element": int(e.get("element")), "screen": keep_i})
            else:
                new_lst.append(e)
        # 如果 src 恰好是 keep，自身出边将统一在后面覆盖
        if src != keep_i and changed:
            utg[src] = _dedupe([x for x in new_lst if x.get("screen") != src])
            out_changed.add(src)

    # 覆盖 keep 的出边
    if keep_i >= len(utg):
        # 扩容 utg
        utg.extend([[] for _ in range(keep_i - len(utg) + 1)])
    utg[keep_i] = _dedupe(keep_out)
    out_changed.add(keep_i)

    # --- 5) 更新 indexList（把 removed 替换为 keep，然后去重） ---
    index_changed = False
    if isinstance(visit_list, list) and visit_list:
        new_visit = []
        for x in visit_list:
            try:
                xi = int(x)
            except Exception:
                continue
            if xi in removed_indices:
                xi = keep_i
                index_changed = True
            new_visit.append(xi)
        # 去重但保顺序
        ordered = []
        seen = set()
        for x in new_visit:
            if x in seen:
                index_changed = True
                continue
            seen.add(x); ordered.append(x)
        visit_list = ordered

    # --- 6) 更新 positions（删除被移除节点的坐标；保留 keep 坐标不变） ---
    pos_removed_labels = []
    for ri in removed_indices:
        lbl = f"{ri}_screenshot.jpg"
        if lbl in positions:
            pos_removed_labels.append(lbl)
            positions.pop(lbl, None)

    # --- 7) 写回或 dry-run ---
    written_leaf = []
    written_vh   = []
    removed_leaf = []
    removed_vh   = []
    if not dry_run:
        # 写 Leaf/VH：只写 keep；被移除的 Leaf/VH 可选择保留或删除。
        write_json(os.path.join(target, f"{keep_prefix}_Leaf.json"), merged_leaf)
        written_leaf.append(f"{keep_prefix}_Leaf.json")
        write_json(os.path.join(target, f"{keep_prefix}_VH.json"), keep_vh)
        written_vh.append(f"{keep_prefix}_VH.json")

        # 可选：删除 removed 的 Leaf/VH（避免后续再次被读到）
        for ri, rp in remove_norm:
            lp = os.path.join(target, f"{rp}_Leaf.json")
            vp = os.path.join(target, f"{rp}_VH.json")
            if os.path.exists(lp):
                try:
                    os.remove(lp)
                    removed_leaf.append(f"{rp}_Leaf.json")
                except Exception:
                    pass
            if os.path.exists(vp):
                try:
                    os.remove(vp)
                    removed_vh.append(f"{rp}_VH.json")
                except Exception:
                    pass

        # 写 utg / indexList / positions
        write_json(os.path.join(target, "utg.json"), utg)
        write_json(os.path.join(target, "indexList.json"), visit_list)
        write_json(os.path.join(target, "positions.json"), positions)

    return jsonify({
        "ok": True,
        "changes": {
          "utg_out_changed": sorted(list(out_changed)),
          "utg_in_changed": sorted(list(in_changed)),
          "leaf_written": written_leaf,
          "vh_written": written_vh,
          "removed_leaf": removed_leaf,
          "removed_vh": removed_vh,
          "positions_removed": pos_removed_labels,
          "indexList_changed": bool(index_changed)
        },
        "result_summary": {
          "keep": keep_i,
          "removed": removed_indices,
          "keep_leaf_count": len(merged_leaf),
          "keep_vh_keys": len(keep_vh.keys()) if isinstance(keep_vh, dict) else 0
        }
    })



#似乎获取target_dir的方法目前有点奇怪啊，mark一下，应该要改
def load_web_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_target_dir():
    cfg = load_web_config()
    return cfg.get(TARGET_KEY)

def set_target_dir(path):
    cfg = load_web_config()
    cfg[TARGET_KEY] = path
    save_config(cfg)

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.post("/api/pick-folder")
def pick_folder():
    """
    方式A（推荐，简单）：前端传路径字符串（本地部署时效果最佳）
    方式B（可选）：如果你在本机运行，可以换成 tkinter.filedialog.askdirectory() 打开原生对话框
    """
    data = request.get_json(force=True)
    folder = (data or {}).get("path")
    if not folder:
        return jsonify({"ok": False, "error": "Missing 'path'"}), 400
    if not os.path.isdir(folder):
        return jsonify({"ok": False, "error": f"Directory not found: {folder}"}), 404
    set_target_dir(folder)
    return jsonify({"ok": True, "path": folder})

@app.get("/api/refresh")
def refresh():
    target = get_target_dir()
    if not target or not os.path.isdir(target):
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400

    # 读取核心文件
    utg = load_json(os.path.join(target, "utg.json"), default=[])
    visit_list = load_json(os.path.join(target, "indexList.json"), default=[])
    positions = load_json(os.path.join(target, "positions.json"), default={})

    # 收集节点相关资源
    # 节点命名以 <idx>_screenshot.jpg 为准，label/id 取这个文件名
    nodes = []
    leaf_list = []
    vh_list = []
    images = []

    # 找出所有 *_screenshot.jpg
    for name in sorted(os.listdir(target)):
        if name.endswith("_screenshot.jpg"):
            label = name
            # 使用可缓存的静态访问URL，而不是 base64
            node = {
                "id": label,
                "label": label,
                "imageUrl": f"/files/{label}",
                # 若 positions.json 有记录就返回给前端
                "position": positions.get(label)  # {"x":..., "y":...} or None
            }
            nodes.append(node)

    # 读取 leaf/vh（以文件是否存在为准）
    for n in nodes:
        idx = n["label"].split("_")[0]
        leaf_path = os.path.join(target, f"{idx}_Leaf.json")
        if os.path.exists(leaf_path):
            leaf_list.append({
                "data": { "id": f"{idx}_Leaf.json", "value": load_json(leaf_path, default=[]) }
            })
        vh_path = os.path.join(target, f"{idx}_VH.json")
        if os.path.exists(vh_path):
            vh_list.append({
                "data": { "id": f"{idx}_VH.json", "value": load_json(vh_path, default={}) }
            })

    return jsonify({
        "ok": True,
        "nodes": nodes,
        "utg": utg,
        "visitList": visit_list,
        "leafJSON": leaf_list,
        "vhJSON": vh_list
    })

@app.get("/files/<path:filename>")
def serve_files(filename):
    # 安全地限制在目标目录
    target = get_target_dir()
    if not target or not os.path.isdir(target):
        return "Target folder is not set", 400
    safe = os.path.abspath(os.path.join(target, filename))
    if not safe.startswith(os.path.abspath(target)):
        return "Forbidden", 403
    if not os.path.exists(safe):
        return "Not Found", 404
    d = os.path.dirname(safe)
    fn = os.path.basename(safe)
    return send_from_directory(d, fn)

@app.post("/api/save-positions")
def save_positions():
    """
    接收：{ positions: { "<label>": {"x": float, "y": float}, ... } }
    """
    target = get_target_dir()
    if not target:
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400
    data = request.get_json(force=True) or {}
    positions = data.get("positions", {})
    pos_path = os.path.join(target, "positions.json")
    write_json(pos_path, positions)
    return jsonify({"ok": True})

@app.post("/api/save-batch")
def save_batch():
    """
    前端在“合并节点、修改UTG、编辑Leaf/VH 等操作完成后”
    将最新整体状态（或局部变更）一次性提交：

    {
      "utg": [...],
      "visitList": [...],
      "leafJSON": [ { "data": { "id": "i_Leaf.json", "value": [...] } }, ... ],
      "vhJSON":   [ { "data": { "id": "i_VH.json",   "value": {...} } }, ... ],
      "positions": { "<label>": {"x":..,"y":..}, ... }   # 可选
    }
    """
    target = get_target_dir()
    if not target:
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400

    payload = request.get_json(force=True) or {}

    # utg / visitList
    if "utg" in payload:
        write_json(os.path.join(target, "utg.json"), payload["utg"])
    if "visitList" in payload:
        write_json(os.path.join(target, "indexList.json"), payload["visitList"])

    # leafJSON
    for item in payload.get("leafJSON", []):
        d = (item or {}).get("data", {})
        _id = d.get("id")
        if _id and _id.endswith("_Leaf.json"):
            write_json(os.path.join(target, _id), d.get("value", []))

    # vhJSON
    for item in payload.get("vhJSON", []):
        d = (item or {}).get("data", {})
        _id = d.get("id")
        if _id and _id.endswith("_VH.json"):
            write_json(os.path.join(target, _id), d.get("value", {}))

    # positions（可选）
    if "positions" in payload:
        write_json(os.path.join(target, "positions.json"), payload["positions"])

    return jsonify({"ok": True})

if __name__ == "__main__":
    # 本地开发：python app_server.py
    # 访问接口：http://127.0.0.1:5000
    app.run(host="127.0.0.1", port=5000, debug=True)

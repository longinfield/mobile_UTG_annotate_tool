# app_server.py
import os, json
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS  # 同源时不需要；保留也不妨

"""
目标数据目录结构（示例）：
<target_dir>/
  ├─ utg.json
  ├─ indexList.json
  ├─ <i>_Leaf.json
  ├─ <i>_VH.json
  └─ <i>_screenshot.jpg

本服务还会写：
  └─ positions.json
"""
#desktop/appflating/static/appData/hk_ust_student_cleared
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_ROOT = os.path.join(PROJECT_ROOT, "templates")  # 你说的 template 目录
# 如果你把 app.js / styles.css 放在 static/，把下面的 static_folder 改成 os.path.join(PROJECT_ROOT, "static")
STATIC_FOLDER = os.path.join(PROJECT_ROOT, "static")
STATIC_URLPATH = ""  # 让 /app.js /styles.css 可直接访问

app = Flask(
    __name__,
    template_folder=TEMPLATE_ROOT,
    static_folder=STATIC_FOLDER,
    static_url_path=STATIC_URLPATH
)
CORS(app)

CONFIG_PATH = os.path.join(PROJECT_ROOT, "server_config.json")
TARGET_KEY  = "target_dir"

# ---------- 小工具 ----------
def load_appflat_config():
    return json.load(open(CONFIG_PATH, "r", encoding="utf-8")) if os.path.exists(CONFIG_PATH) else {}

def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_target_dir():
    return load_appflat_config().get(TARGET_KEY)

def set_target_dir(path: str):
    cfg = load_appflat_config(); cfg[TARGET_KEY] = path; save_config(cfg)

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- 页面 ----------
@app.get("/")
def index_page():
    # 渲染 template/index.html
    return render_template("index.html")

# ---------- 选择目录 ----------
@app.post("/api/pick-folder")
def pick_folder():
    data = request.get_json(force=True) or {}
    folder = data.get("path")
    folder_path = os.path.join(PROJECT_ROOT,"static","appData",folder)
    if not folder:
        return jsonify({"ok": False, "error": "Missing 'path'"}), 400
    if not os.path.isdir(folder_path):
        return jsonify({"ok": False, "error": f"Directory not found: {folder_path}"}), 404
    set_target_dir(folder_path)
    return jsonify({"ok": True, "path": folder_path})

# ---------- 目标目录里图片/文件（截图等） ----------
@app.get("/files/<path:filename>")
def serve_files(filename):
    target = get_target_dir()
    if not target or not os.path.isdir(target):
        return "Target folder is not set", 400
    safe = os.path.abspath(os.path.join(target, filename))
    if not safe.startswith(os.path.abspath(target)):
        return "Forbidden", 403
    if not os.path.exists(safe):
        return "Not Found", 404
    return send_from_directory(os.path.dirname(safe), os.path.basename(safe))

# ---------- 刷新 ----------
@app.get("/api/refresh")
def refresh():
    target = get_target_dir()
    if not target or not os.path.isdir(target):
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400
    utg = load_json(os.path.join(target, "utg.json"), default=[])
    visit_list = load_json(os.path.join(target, "indexList.json"), default=[])
    positions = load_json(os.path.join(target, "positions.json"), default={})

    nodes = []
    for name in sorted(os.listdir(target)):
        if name.endswith("_screenshot.jpg"):
            nodes.append({
                "id": name,
                "label": name,
                "imageUrl": f"/files/{name}",
                "position": positions.get(name)
            })

    leaf_list, vh_list = [], []
    for n in nodes:
        idx = n["label"].split("_")[0]
        lp = os.path.join(target, f"{idx}_Leaf.json")
        if os.path.exists(lp):
            leaf_list.append({"data": {"id": f"{idx}_Leaf.json", "value": load_json(lp, default=[])}})
        vp = os.path.join(target, f"{idx}_VH.json")
        if os.path.exists(vp):
            vh_list.append({"data": {"id": f"{idx}_VH.json", "value": load_json(vp, default={})}})

    return jsonify({"ok": True, "nodes": nodes, "utg": utg, "visitList": visit_list, "leafJSON": leaf_list, "vhJSON": vh_list})

# ---------- 位置保存 ----------
@app.post("/api/save-positions")
def save_positions():
    target = get_target_dir()
    if not target:
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400
    data = request.get_json(force=True) or {}
    positions = data.get("positions", {})
    write_json(os.path.join(target, "positions.json"), positions)
    return jsonify({"ok": True})

# ---------- 批量保存（utg/visit/leaf/vh/positions） ----------
@app.post("/api/save-batch")
def save_batch():
    target = get_target_dir()
    if not target:
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400

    payload = request.get_json(force=True) or {}
    if "utg" in payload:
        write_json(os.path.join(target, "utg.json"), payload["utg"])
    if "visitList" in payload:
        write_json(os.path.join(target, "indexList.json"), payload["visitList"])

    for item in payload.get("leafJSON", []):
        d = (item or {}).get("data", {})
        _id = d.get("id")
        if _id and _id.endswith("_Leaf.json"):
            write_json(os.path.join(target, _id), d.get("value", []))

    for item in payload.get("vhJSON", []):
        d = (item or {}).get("data", {})
        _id = d.get("id")
        if _id and _id.endswith("_VH.json"):
            write_json(os.path.join(target, _id), d.get("value", {}))

    if "positions" in payload:
        write_json(os.path.join(target, "positions.json"), payload["positions"])

    return jsonify({"ok": True})

# ---------- 合并（后端运算） ----------
def _norm_id(nid):
    if isinstance(nid, int):
        i = nid
    else:
        s = str(nid).strip()
        if s.endswith("_screenshot.jpg"):
            s = s.replace("_screenshot.jpg", "")
        i = int(s)
    return i, str(i)

def _bbox_similar(a, b, thr=10):
    if a.get("text") != b.get("text"):
        return False
    return (
        abs(a.get("boundLeft", 0)   - b.get("boundLeft", 0))   < thr and
        abs(a.get("boundTop", 0)    - b.get("boundTop", 0))    < thr and
        abs(a.get("boundRight", 0)  - b.get("boundRight", 0))  < thr and
        abs(a.get("boundBottom", 0) - b.get("boundBottom", 0)) < thr
    )

def _merge_bbox_lists(lists, thr=10):
    #remaps存储了原本lists中的没一个leaf中的元素与merge之后的merged 中的元素的对应情况,形如:
    #remaps = [{0:0,1:1,2:2,3,3}, {0:4,1:0,2:5}] 即代表了第一个leaf全部存入了merge,第二个leaf在存入的时候第二个leaf的0号元素就是merge的4号，而其1号元素与merge的0号元素重合，因此它不存入，其2号元素继续存入merged则成为merged中的5号元素。
    merged = lists[0]
    remaps = []
    remaps.append({i: i for i in range(len(lists[0]))})
    candidate_lists = lists[1:]
    for leaf in candidate_lists:
        mapping = {}
        for idx, elem in enumerate(leaf):
            found = -1
            for j, ex in enumerate(merged):
                if _bbox_similar(ex, elem, thr=thr):
                    found = j; break
            if found == -1:
                merged.append(elem); found = len(merged) - 1
            mapping[idx] = found
        remaps.append(mapping)
    return merged, remaps

def _dedupe_edges(seq):
    seen = set()
    out = []
    for x in seq:
        key = (int(x.get("element")), int(x.get("screen")))
        if key in seen:
            continue
        seen.add(key)
        out.append({"element": key[0], "screen": key[1]})
    return out

@app.post("/api/merge")
def merge_nodes_api():
    #在一个文件夹下存储了一个UI页面所构成的graph的所有元数据。其中每个节点的名称为一个序号+_screenshot.jpg。例如"0_screenshot.jpg"。每个节点的元数据名称形如"0_leaf.json"。另有两个数组分别存储每个节点的位置信息和访问次数信息。存储位置信息的数组position形如[{"0_screenshot.jpg": {"x":x_pos,"y":y_pos}},...]，存储访问次数信息的数组visit_list为一个整数数组。此外各个节点之间的边的连接情况存储在utg数组中。utg数组形如:[[{element:0,"screen":1},{element:0,"screen":1,}],...]。每个节点名称中的序号与他们在utg数组中的位置一致。utg数组中的每个元素代表了对应节点的出边情况。element字段表示该节点产生出边的元素编号，screen字段代表了该节点出边的目标节点的序号(也就是目标节点名称中的数字部份)。现在给定一组节点序号，例如[2,4,5,6]，需要将给定的这一组节点合并为一个新的节点，新的节点的序号排在所有节点的最末，新的节点需要继承合并前这些节点的所有出边情况，其他各个节点向合并前的节点的入边情况也要归于新的节点。此外新的节点对应的position信息应当为合并前节点的平均位置，新的节点的访问次数信息为合并前节点的访问次数之最小值。请写出代码解决这一问题。由于节点的合并会影响到所有节点在utg数组中的新的序号，进而影响他们的出边的表征，以及他们的节点名称，请妥善考虑这些因素。给出正确的算法。
    target = get_target_dir()
    if not target or not os.path.isdir(target):
        return jsonify({"ok": False, "error": "Target folder is not set"}), 400

    data = request.get_json(force=True) or {}
    if "keep" not in data or "remove" not in data:
        return jsonify({"ok": False, "error": "Missing 'keep' or 'remove'"}), 400

    print("merge data", data)
    thr     = int(data.get("bbox_threshold", 10))
    dry_run = bool(data.get("dry_run", False))

    keep_i, keep_prefix = _norm_id(data["keep"])
    remove_norm = []
    for nid in data["remove"]:
        ri, rp = _norm_id(nid)
        if ri == keep_i: continue
        remove_norm.append((ri, rp))
    if not remove_norm:
        return jsonify({"ok": False, "error": "Nothing to merge"}), 400
    removed_indices = sorted({ri for ri, _ in remove_norm})

    utg        = load_json(os.path.join(target, "utg.json"), default=[])
    visit_list = load_json(os.path.join(target, "indexList.json"), default=[])
    positions  = load_json(os.path.join(target, "positions.json"), default={})

    # 原节点总数
    n = len(utg)
    merge_set = set(removed_indices)
    merge_set.add(keep_i)
    print("merge_set", merge_set)

    # 1. 保留节点与原->新编号映射
    preserved = []   # 保留下来的节点原始编号列表
    mapping = {}     # 原编号 -> 新编号
    new_index = 0
    for i in range(n):
        if i not in merge_set:
            preserved.append(i)
            mapping[i] = new_index
            new_index += 1
    # 新节点编号，新节点将放在最后
    new_id = new_index

    # 2. 更新 utg 数组
    new_utg = []
    # 2a. 处理保留节点的出边更新：遍历保留节点原来的 utg
    for i in preserved:
        new_edges = []
        for edge in utg[i]:
            dest = edge["screen"]
            # 如果目标在待合并集合内，则更新目标为新节点
            if dest in merge_set:
                dest_new = new_id
            else:
                dest_new = mapping[dest]  # 保留节点编号更新
            # 这里 element 字段一般记录边产生时的元素编号，
            # 如果需要更新也可以处理；示例中暂保持不变
            new_edges.append({"element": edge["element"], "screen": dest_new})
        new_utg.append(new_edges)

    # 2b. 新节点的出边：合并所有待合并节点的出边

    # 2b-1 Leaf 合并
    leaf_lists = []
    keep_leaf_path = os.path.join(target, f"{keep_prefix}_Leaf.json")
    if os.path.exists(keep_leaf_path):
        leaf_lists.append(load_json(keep_leaf_path, default=[]))
    print("leaf_lists", leaf_lists)
    for ri in removed_indices:
        p = os.path.join(target, str(ri)+"_Leaf.json")
        if os.path.exists(p):
            leaf_lists.append(load_json(p, default=[]))
    merged_leaf, remaps = _merge_bbox_lists(leaf_lists, thr=thr) if leaf_lists else ([], [])

    # 2b-2 VH 合并
    keep_vh_lists = []
    keep_vh_path = os.path.join(target, f"{keep_prefix}_VH.json")
    if os.path.exists(keep_vh_path):
        keep_vh = load_json(keep_vh_path, default={})
        keep_vh_lists.append(keep_vh)
    for ri in removed_indices:
        p = os.path.join(target, str(ri)+"_VH.json")
        if os.path.exists(p):
            v = load_json(p, default={})
            keep_vh_lists.append(v)
    merged_vh, _ = _merge_bbox_lists(keep_vh_lists, thr=thr) if keep_vh_lists else ([], [])

    # 2b-3 出边合并
    new_keep_out = []
    def _get_out(i): return utg[i] if i < len(utg) and isinstance(utg[i], list) else []
    keep_out = list(_get_out(keep_i))
    for e in keep_out:
        tgt = int(e.get("screen"))
        if tgt in merge_set: continue #避免自环
        new_keep_out.append({"element": int(e.get("element")), "screen": mapping[tgt]})
    for idx, ri in enumerate(removed_indices):
        ele_remap = remaps[idx+1]#此处+1是因为remaps[0]存的是keep的remap
        for e in _get_out(ri):
            tgt = int(e.get("screen"))
            if tgt in merge_set : continue #避免自环
            new_keep_out.append({"element": ele_remap[int(e.get("element"))], "screen": mapping[tgt]})
    new_keep_out = _dedupe_edges(new_keep_out) #此处最好再在new_keepout开头插入一个{"element":-1,"screen":new_id}
    new_utg.append(new_keep_out)

    # 3. 更新 position 数组
    # 对于保留节点，文件名也要更新；假设 positions 是一个列表，每个元素类似 { "i_screenshot.jpg": {"x":..., "y":...} }
    new_positions = {}
    for i in preserved:
        # 找到原节点对应位置字典
        key_old = f"{i}_screenshot.jpg"
        pos_info = positions[key_old]
        key_new = f"{mapping[i]}_screenshot.jpg"
        new_positions[key_new]=pos_info
    # 新节点位置为被合并节点位置的平均值
    sum_x = 0
    sum_y = 0
    count = 0
    for i in removed_indices:
        key_old = f"{i}_screenshot.jpg"
        pos_info = positions[key_old]
        sum_x += pos_info["x"]
        sum_y += pos_info["y"]
        count += 1
    avg_x = sum_x / count
    avg_y = sum_y / count
    key_new = f"{new_id}_screenshot.jpg"
    new_positions[key_new]={"x": avg_x, "y": avg_y}

    # 4. 更新 visit_list 列表
    new_visit = []
    # 保留节点的访问次数直接复制
    for i in preserved:
        new_visit.append(visit_list[i])
    # 新节点访问次数为待合并节点中最小的
    new_visit_value = visit_list[keep_i]
    new_visit.append(new_visit_value)

    # 第一阶段：全部临时重命名，确保后续改名时不会碰撞
    for filename in os.listdir(target):
        # 需处理两个类型文件：截图文件 (_screenshot.jpg) 和元数据文件 (_leaf.json)
        if filename.endswith("_screenshot.jpg") or filename.endswith("_leaf.json"):
            old_path = os.path.join(target, filename)
            temp_path = os.path.join(target, "tmp_" + filename)
            os.rename(old_path, temp_path)

    # 第二阶段：按照类型重新命名
    # 获取文件列表（含临时前缀）后进行遍历重命名
    for filename in os.listdir(target):
        if not filename.startswith("tmp_"):
            continue
        # filename 不带 "tmp_" 前缀的部分
        real_name = filename[4:]
        new_final_name = None

        # 判断类型
        if real_name.endswith("_screenshot.jpg"):
            parts = real_name.split("_")
            try:
                node_num = int(parts[0])
            except:
                continue
            # 保留节点或合并节点
            if node_num not in merge_set:
                # 保留节点：重命名为 mapping[node_num]_screenshot.jpg
                new_final_name = f"{mapping[node_num]}_screenshot.jpg"
            else:
                # 合并节点
                if node_num == keep_i:
                    # 合并节点中序号最小的文件为留存文件，重命名为 new_id_screenshot.jpg
                    new_final_name = f"{new_id}_screenshot.jpg"
                else:
                    # 其它合并节点更新为 None，后面删除
                    new_final_name = None

        elif real_name.endswith("_Leaf.json"):
            parts = real_name.split("_")
            try:
                node_num = int(parts[0])
            except:
                continue
            if node_num not in merge_set:
                new_final_name = f"{mapping[node_num]}_Leaf.json"
            else:
                if node_num == keep_i:
                    new_final_name = f"{new_id}_Leaf.json"
                else:
                    new_final_name = None

        cur_temp_path = os.path.join(target, filename)
        if new_final_name:
            new_final_path = os.path.join(target, new_final_name)
            os.rename(cur_temp_path, new_final_path)
        else:
            # 不需要保留的文件，直接删除
            os.remove(cur_temp_path)

    if not dry_run:
        write_json(os.path.join(target, str(new_id)+"_Leaf.json"), merged_leaf)
        write_json(os.path.join(target, str(new_id)+"_VH.json"),   merged_vh)
        write_json(os.path.join(target, "utg.json"),                 utg)
        write_json(os.path.join(target, "indexList.json"),           visit_list)
        write_json(os.path.join(target, "positions.json"),           positions)

    return jsonify({
        "ok": True,
        "result_summary": {
            "keep": keep_i, "removed": removed_indices,
            "keep_leaf_count": len(merged_leaf),
            "keep_vh_keys": len(keep_vh) if isinstance(keep_vh, dict) else 0
        }
    })

if __name__ == "__main__":
    # 运行：python app_server.py  →  http://127.0.0.1:5000/
    app.run(host="127.0.0.1", port=5000, debug=True)

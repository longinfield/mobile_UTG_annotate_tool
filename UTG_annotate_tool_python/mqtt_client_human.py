import os
import base64
from datetime import datetime
import threading
import time
import json
import io
from queue import Queue

import paho.mqtt.client as mqtt
from PIL import Image
import cv2 as cv
import numpy as np

from utils import *  # 依赖：worthness_judge, screenRelocation, same_screen_discriminator,
                     # smart_back(如果还要用就留着), ele_set_update_rulebased,
                     # generate_navigation_box_with_GPT, 等

# ============== 全局对象 ==============

# 全局 MQTT client（在 main 里初始化）
client = None

# GUI / 人工判断任务队列：回调线程把任务丢进队列，主线程来处理
gui_task_queue = Queue()

# 可选：如果后面你要用到
isInitialQuery = True
previewQuery = {"preStep": None, "postStep": None, "x": None, "y": None}


# ============== MQTT 回调 ==============

def on_connect(mqtt_client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully!")
        # 连接成功后订阅多个主题
        mqtt_client.subscribe("fileTopic", qos=1)
        mqtt_client.subscribe("tempScreenTopic", qos=1)
        mqtt_client.subscribe("smartBackTopic", qos=1)
        mqtt_client.subscribe("screenshotTopic", qos=1)
        mqtt_client.subscribe("query", qos=1)
        mqtt_client.subscribe("previewVM", qos=1)
        mqtt_client.subscribe("previewAgent", qos=1)
        mqtt_client.subscribe("stepOperateAgent", qos=1)
        mqtt_client.subscribe("textTopic", qos=1)
    else:
        print(f"Failed to connect, return code {rc}")


def on_message(mqtt_client, userdata, msg):
    """
    注意：这个回调在 paho 的网络线程中执行。
    这里 **不能** 调用 cv.imshow / cv.waitKey / input 等 GUI 或阻塞式交互。
    """
    global isInitialQuery
    global previewQuery

    try:
        if msg.topic == "textTopic":
            # 文字类 topic，直接处理并快速回传
            text = handle_text(msg.payload.decode())
            call_back_data = {"screenNum": 1, "isSame": True, "echo": text}
            call_back_message = json.dumps(call_back_data)
            info = mqtt_client.publish("myCloud", call_back_message, qos=1)
            print("publish textTopic callback, mid:", info.mid)
            return

        # 其他 topic，先尝试解析 JSON
        if msg.topic in [
            "fileTopic",
            "screenshotTopic",
            "smartBackTopic",
            "tempScreenTopic",
            "query",
            "previewVM",
            "previewAgent",
            "stepOperateAgent",
        ]:
            try:
                query_data = json.loads(msg.payload.decode())
            except Exception as e:
                print(f"Failed to decode JSON from topic {msg.topic}: {e}")
                return
        else:
            # 其他暂未处理的 topic
            print("Received message from unhandled topic:", msg.topic)
            return

        # ---- fileTopic：只做文件保存，逻辑很轻，在回调线程里执行即可 ----
        if msg.topic == "fileTopic":
            handle_file(query_data)
            return

        # ---- screenshotTopic：保存截图 + 简单回调 ----
        if msg.topic == "screenshotTopic":
            dir_path, image_path, file_name, ui_elements = handle_Screen(query_data, isTemp=False)
            if not image_path:
                print("screenshotTopic: handle_Screen failed")
                return

            print("save screenshot to", image_path)
            call_back_data = {"screenNum": 0, "isSame": False}
            call_back_message = json.dumps(call_back_data)
            info = mqtt_client.publish("myCloud", call_back_message, qos=1)
            print("screenshotTopic callback mid:", info.mid)
            return

        # ---- smartBackTopic：现在改为“进入 GUI 任务”，由主线程让用户点击坐标 ----
        if msg.topic == "smartBackTopic":
            print("receive smartBackTopic, enqueue smart_back task")
            gui_task_queue.put(("smart_back", query_data))
            return

        # ---- tempScreenTopic：这边逻辑重，而且有 cv.imshow + input
        #      所以只把任务丢进队列，由主线程处理 ----
        if msg.topic == "tempScreenTopic":
            gui_task_queue.put(("temp_screen", query_data))
            print("tempScreenTopic: task enqueued")
            return

        # ---- query：处理单个图 + 问题，调用 GPT，回传定位 + 指令 ----
        if msg.topic == "query":
            image_path = None
            question = None

            for key, value in query_data.items():
                if key == "image":
                    image_path = handle_query_image(value)
                elif key == "question":
                    question = handle_text(value)

            print("query image_path:", image_path, "question:", question)
            if not image_path or not question:
                print("query: missing image or question")
                return

            position, instruction = generate_navigation_box_with_GPT(image_path, question)
            print("position", position)
            print("instruction", instruction)

            call_back_data = {"position": position, "instruction": instruction}
            call_back_message = json.dumps(call_back_data)

            info = mqtt_client.publish("myCloud", call_back_message, qos=1)
            print("query callback mid:", info.mid)
            return

    except Exception as e:
        print(f"Failed to process the message from topic {msg.topic}: {e}")


# ============== 各种工具函数 ==============

def resize_image(input_path, output_path):
    with Image.open(input_path) as img:
        original_width, original_height = img.size
        new_width = original_width // 4
        new_height = original_height // 4
        resized_img = img.resize((new_width, new_height))
        resized_img.save(output_path)


def compress_and_encode_image(file_path, output_format='PNG', quality=50):
    with Image.open(file_path) as img:
        buffer = io.BytesIO()
        img.save(buffer, format=output_format, quality=quality)
        byte_data = buffer.getvalue()
        encoded_data = base64.b64encode(byte_data).decode('utf-8')
        return encoded_data


def handle_query_image(msg_str):
    """
    处理 query topic 里的 base64 图片字符串
    """
    try:
        image_folder = "image"
        if not os.path.exists(image_folder):
            os.makedirs(image_folder)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        image_path = os.path.join(image_folder, f"{timestamp}.jpg")

        transfer_base64_to_image(msg_str, image_path)
        return image_path
    except Exception as e:
        print(f"Failed to process the image in query: {e}")
        return None


def handle_file(data):
    try:
        file_name = data.get("fileName")
        package_name = data.get("packageName")
        base64_data = data.get("base64")

        dir_path = os.path.join(os.getcwd(), 'static', 'appData', package_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        if file_name and base64_data:
            file_path = os.path.join(dir_path, file_name)
            file_content = base64.b64decode(base64_data)
            with open(file_path, "wb") as file_obj:
                file_obj.write(file_content)
            print(f"File saved to {file_path}")
        else:
            print("Invalid file data format. Missing 'fileName' or 'base64'.")
    except Exception as e:
        print(f"Failed to process the file: {e}")


def handle_text(msg):
    try:
        text_message = msg
        print(f"Received text: {text_message}")
        return text_message
    except Exception as e:
        print(f"Failed to process the text message: {e}")
        return "error"


def transfer_base64_to_image(msg, image_path):
    """
    把 base64 字符串保存为图片文件。
    支持前缀 "data:image/jpeg;base64," 或纯 base64。
    """
    if msg.startswith("data:image/jpeg;base64,"):
        message_payload = msg.replace("data:image/jpeg;base64,", "")
    else:
        message_payload = msg

    image_data = base64.b64decode(message_payload)

    with open(image_path, "wb") as image_file:
        image_file.write(image_data)

    print(f"Image saved to {image_path}")


def handle_back_json(data):
    try:
        prior_index = data.get("prior")
        package_name = data.get("packageName")
        current_index = data.get("current")
        print("prior screen", prior_index, "current_index", current_index)

        dir_path = os.path.join(os.getcwd(), 'static', 'appData', package_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        prior_image_path = os.path.join(dir_path, f"{prior_index}_screenshot.jpg")
        current_image_path = os.path.join(dir_path, f"{current_index}_screenshot.jpg")
        current_json_path = os.path.join(dir_path, f"{current_index}_VH.json")
        return dir_path, prior_image_path, current_image_path, current_json_path
    except Exception as e:
        print(f"Failed to process the image: {e}")
        return None, None, None, None

def handle_back_Screen(data):
    try:
        file_name = data.get("text")
        package_name = data.get("packageName")
        base64_data = data.get("image")
        node_array = data.get("nodeArray")

        ui_elements = json.loads(node_array) if node_array else []

        dir_path = os.path.join(os.getcwd(), 'static', 'appData', package_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        image_path = os.path.join(dir_path, "backfrom.jpg")

        transfer_base64_to_image(base64_data, image_path)
        return dir_path, image_path, file_name, ui_elements
    except Exception as e:
        print(f"Failed to process the image: {e}")
        return None, None, None, None


def handle_Screen(data, isTemp=False):
    try:
        file_name = data.get("text")
        package_name = data.get("packageName")
        base64_data = data.get("image")
        node_array = data.get("nodeArray")

        ui_elements = json.loads(node_array) if node_array else []

        dir_path = os.path.join(os.getcwd(), 'static', 'appData', package_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        if isTemp:
            image_path = os.path.join(dir_path, "tempScreen.jpg")
        else:
            image_path = os.path.join(dir_path, file_name)

        transfer_base64_to_image(base64_data, image_path)
        return dir_path, image_path, file_name, ui_elements
    except Exception as e:
        print(f"Failed to process the image: {e}")
        return None, None, None, None


# ============== 主线程：smartBackTopic 的点击逻辑 ==============

def process_smartback_task(query_data):
    """
    smartBackTopic 的主线程处理：
    1. 保存 tempScreen.jpg
    2. 用 OpenCV 显示图片，用户在图片上点击一次，记录 (x, y)
    3. 把截图 + 点击坐标 + ui_elements 保存到 smartback 文件夹
    4. 把 (x, y) 回传到 BackTopic
    """
    global client

    dir_path, image_path, file_name, ui_elements = handle_back_Screen(query_data)
    if not image_path:
        print("process_smartback_task: handle_Screen failed")
        return

    img = cv.imread(image_path)
    #prior_img = cv.imread(os.path.join(dir_path, "tempScreen.jpg"))
    if img is None:
        print("process_smartback_task: failed to read image:", image_path)
        return

    click_point = {"x": None, "y": None}
    win_name = "smartBack - 请点击回退位置"

    # 水平拼接图像
    #result = np.hstack((img, prior_img))

    def mouse_callback(event, x, y, flags, param):
        if event == cv.EVENT_LBUTTONDOWN:
            click_point["x"] = x
            click_point["y"] = y
            # 在图上画一个红点，方便你确认点击位置（存的时候也会带上这个点）
            cv.circle(img, (x, y), 8, (0, 0, 255), -1)
            cv.imshow(win_name, img)

    cv.imshow(win_name, img)
    cv.setMouseCallback(win_name, mouse_callback)
    print("smartBack: 请在弹出的窗口中点击一个界面元素以离开当前页面。")

    # 等待用户点击
    while True:
        key = cv.waitKey(20) & 0xFF
        # 用户点击后，click_point 会被设置
        if click_point["x"] is not None:
            break
        # 如果用户按 q 也允许退出
        if key == ord('q'):
            break

    cv.destroyAllWindows()

    coord_x, coord_y = click_point["x"], click_point["y"]
    if coord_x is None or coord_y is None:
        print("smartBack: 用户未点击或取消，未获得坐标。")
        return

    # 3. 保存到 smartback 文件夹
    smart_dir = os.path.join(dir_path, "smartback")
    if not os.path.exists(smart_dir):
        os.makedirs(smart_dir)

    timestamp = int(time.time())
    img_name = f"smartback_{timestamp}.jpg"
    json_name = f"smartback_{timestamp}.json"

    img_save_path = os.path.join(smart_dir, img_name)
    cv.imwrite(img_save_path, img)

    record = {
        "image_name": img_name,
        "click_x": coord_x,
        "click_y": coord_y,
        "ui_elements": ui_elements
    }
    json_save_path = os.path.join(smart_dir, json_name)
    with open(json_save_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"smartBack: 保存图片到 {img_save_path}")
    print(f"smartBack: 保存标注到 {json_save_path}")

    # 4. 回传坐标到 BackTopic
    call_back_data = {"coordinate_x": coord_x, "coordinate_y": coord_y}
    call_back_message = json.dumps(call_back_data)

    if client is not None:
        info = client.publish("BackTopic", call_back_message, qos=1)
        print("smartBack publish mid:", info.mid)
        current_time = time.time()
        print("Current timestamp:", current_time)
        print("Current time:", time.ctime(current_time))
        print("smartBack 回传成功")
    else:
        print("client is None, cannot publish smartBack callback")


# ============== 主线程处理 tempScreen 的逻辑（包含 OpenCV GUI + 人工判断） ==============

def process_temp_screen_task(query_data):
    """
    这个函数在 **主线程** 中执行，允许使用 cv.imshow / cv.waitKey / input 等。
    逻辑基本等价于你原来 tempScreenTopic 分支里的代码，只是移了位置。
    """
    global client

    dir_path, image_path, file_name, ui_elements = handle_Screen(query_data, isTemp=True)
    if not image_path:
        print("process_temp_screen_task: handle_Screen failed")
        return

    # screenRelocation
    screenNum, similarity = screenRelocation(dir_path, image_path)
    print("screenNum", screenNum)
    print("similarity", similarity)

    # 初始化这些变量，保证任何路径下都有值
    isSame = False
    page_freeze = True
    new_node_array = []

    # ========== 情况 1：similarity <= 0.8，被认为是新页面 ==========
    if similarity <= 0.7:
        # 先把 tempScreen 保存成真正的截图文件
        with Image.open(image_path) as img:
            img.save(os.path.join(dir_path, file_name))

        isSame = False
        new_node_array = []  # 新页面，后端直接用移动端抓好的 nodeArray 即可

        # --- 价值判断（AI + 人工） ---
        isDeserved, resp = worthness_judge(image_path)
        print("touch point: worthness judgement:", isDeserved)
        print("你是否希望AI助手对当前页面继续深入探索其功能 (Y/N)")

        result_img = cv.imread(image_path)
        cv.imshow("worthness judgement", result_img)
        cv.waitKey(0)
        cv.destroyAllWindows()

        
        human_judgement = input().strip()

        if human_judgement in ["Y", "y"]:
            page_freeze = False
            if isDeserved:
                dir_name = "worth_all_TP"
            else:
                dir_name = "worth_human_FN"
        else:
            page_freeze = True
            if isDeserved:
                dir_name = "noworth_human_FP"
            else:
                dir_name = "noworth_all_TN"

        timestamp = int(time.time())
        f_name = f"worthness_{timestamp}"

        save_dir = os.path.join(dir_path, dir_name)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            print("文件夹已创建<0.8")
        else:
            print("文件夹已存在<0.8")

        cv.imwrite(os.path.join(save_dir, f_name + ".jpg"), result_img)
        with open(os.path.join(save_dir, f_name + ".json"), "w", encoding="utf-8") as f:
            json.dump({f_name: resp}, f, ensure_ascii=False, indent=2)

    # ========== 情况 2：similarity > 0.99，被认为是高度相似 ==========
    elif similarity > 0.99:
        images = [os.path.join(dir_path, f"{screenNum}_screenshot.jpg"), image_path]
        prior_ui_json_path = os.path.join(dir_path, f"{screenNum}_Leaf.json")

        with open(prior_ui_json_path, "r", encoding="utf-8") as f:
            prior_ui_json = json.load(f)

        if len(prior_ui_json) > 0:
            new_node_array = ele_set_update_rulebased(prior_ui_json, images, save_path=prior_ui_json_path)
            print("AI generate new node array (json of a UI screen)", new_node_array)
            isSame = True
            page_freeze = False
        else:
            new_node_array = []
            print("new node array is none for the same but not worth ui screen", new_node_array)
            isSame = True
            page_freeze = True

    # ========== 情况 3：0.8 < similarity <= 0.99，中间区域，需 same_screen_discriminator + 人工 ==========
    else:
        images = [os.path.join(dir_path, f"{screenNum}_screenshot.jpg"), image_path]
        isSame_ai, resp = same_screen_discriminator(images)
        print("touch point: same screen judgement (AI):", isSame_ai)

        im1 = cv.imread(images[0])
        im2 = cv.imread(images[1])
        result_img = np.hstack((im1, im2))

        cv.imshow("same screen judgement", result_img)
        cv.waitKey(0)
        cv.destroyAllWindows()

        print("你觉得当前的两个页面是否为相同页面 (Y/N)")
        human_judgement = input().strip()

        if human_judgement in ["Y", "y"]:
            if isSame_ai:
                dir_name = "same_all_TP"
            else:
                dir_name = "same_human_FN"
            isSame = True
        else:
            if isSame_ai:
                dir_name = "different_human_FP"
            else:
                dir_name = "different_all_TN"
            isSame = False

        timestamp = int(time.time())
        f_name = f"concatenated_{timestamp}"

        save_dir = os.path.join(dir_path, dir_name)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            print("文件夹已创建issame")
        else:
            print("文件夹已存在issame")

        cv.imwrite(os.path.join(save_dir, f_name + ".jpg"), result_img)
        with open(os.path.join(save_dir, f_name + ".json"), "w", encoding="utf-8") as f:
            json.dump({f_name: resp}, f, ensure_ascii=False, indent=2)

        prior_ui_json_path = os.path.join(dir_path, f"{screenNum}_Leaf.json")

        if isSame:
            with open(prior_ui_json_path, "r", encoding="utf-8") as f:
                prior_ui_json = json.load(f)

            if len(prior_ui_json) > 0:
                new_node_array = ele_set_update_rulebased(prior_ui_json, images, save_path=prior_ui_json_path)
                print("AI generate new node array (json of a UI screen)", new_node_array)
                page_freeze = False
            else:
                new_node_array = []
                print("new node array is none for the same but not worth ui screen", new_node_array)
                page_freeze = True
        else:
            # 确认是新页面
            with Image.open(image_path) as img:
                img.save(os.path.join(dir_path, file_name))

            isSame = False
            new_node_array = []

            isDeserved, resp_worth = worthness_judge(image_path)
            print("touch point: worthness judgement:", isDeserved)
            print("你是否希望AI助手对当前页面继续深入探索其功能 (Y/N)")

            img2 = cv.imread(image_path)
            cv.imshow("worthness judgement", img2)
            cv.waitKey(0)
            cv.destroyAllWindows()

            
            human_judgement2 = input().strip()

            if human_judgement2 in ["Y", "y"]:
                page_freeze = False
                if isDeserved:
                    dir_name2 = "worth_all_TP"
                else:
                    dir_name2 = "worth_human_FN"
            else:
                page_freeze = True
                if isDeserved:
                    dir_name2 = "noworth_human_FP"
                else:
                    dir_name2 = "noworth_all_TN"

            timestamp2 = int(time.time())
            f_name2 = f"worthness_{timestamp2}"

            save_dir2 = os.path.join(dir_path, dir_name2)
            if not os.path.exists(save_dir2):
                os.makedirs(save_dir2)
                print("文件夹已创建not_same_worthness")
            else:
                print("文件夹已存在not_same_worthness")

            cv.imwrite(os.path.join(save_dir2, f_name2 + ".jpg"), img2)
            with open(os.path.join(save_dir2, f_name2 + ".json"), "w", encoding="utf-8") as f:
                json.dump({f_name2: resp_worth}, f, ensure_ascii=False, indent=2)

    # ---- 最终统一回传给 myCloud ----
    call_back_data = {
        "screenNum": screenNum,
        "isSame": isSame,
        "page_freeze": page_freeze,
        "new_node_array": new_node_array,
    }
    call_back_message = json.dumps(call_back_data)

    if client is not None:
        info = client.publish("myCloud", call_back_message, qos=1)
        print("tempScreenTopic callback mid:", info.mid)
        current_time = time.time()
        print("Current timestamp:", current_time)
        print("Current time:", time.ctime(current_time))
        print("回传成功")
    else:
        print("client is None, cannot publish tempScreen callback")


# ============== 程序入口：在主线程中跑 GUI 任务循环 ==============

if __name__ == "__main__":
    # 1. 初始化 MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # 如需账号密码，在这里设置：
    # client.username_pw_set("admin", "admin")

    # 连接到 MQTT 代理
    client.connect("", 1883, 60)

    # 2. 启动网络循环（在后台线程中）
    client.loop_start()

    print("MQTT client started. Waiting for messages...")

    # 3. 主线程专门处理 GUI / 人工判断任务
    while True:
        task_type, payload = gui_task_queue.get()  # 阻塞等待任务
        if task_type == "temp_screen":
            process_temp_screen_task(payload)
        elif task_type == "smart_back":
            process_smartback_task(payload)
        else:
            print("Unknown task type:", task_type)

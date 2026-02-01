import json
import os.path
import time

from PIL import Image, ImageDraw
from UI_GPT_model import *
import torch
from torchvision import models, transforms
from PIL import Image
import numpy as np
from torchvision.models import resnet50, ResNet50_Weights
from collections import deque
from json_repair import repair_json
import cv2

configs = load_config()
UI_text_model = UITextModel(model=configs["OPENAI_API_MODEL"], temperature=configs["TEMPERATURE"], max_tokens=configs["MAX_TOKENS"])
mllm = OpenAIModel(model=configs["OPENAI_API_MODEL"],
                       temperature=configs["TEMPERATURE"],
                       max_tokens=configs["MAX_TOKENS"])
# 加载预训练的ResNet50模型
model = resnet50(weights=ResNet50_Weights.DEFAULT)
model.eval()

# 判断给定页面是否值得被探索,如果值得探索返回True,否则返回False
def worthness_judge(img_path):
    _, resp = mllm.single_UI_worthness(img_path)
    if ("Yes" in resp[-5:] or "Yes" in resp[0:5]):
        return True, resp
    else:
        return False, resp

def same_screen_discriminator(images):
    _, resp = mllm.same_screen_recognition_few_shot_prompot(images)
    if ("Yes" in resp[-5:] or "Yes" in resp[0:5]):
        return True,resp
    else:
        return False,resp

def ele_set_update(node_array, prior_ui_json_path, images):
    #load screen的json，然后和node_array一起塞给gpt
    prior_json = load_json(prior_ui_json_path)
    elements = [prior_json,node_array]
    _ , new_node_array = mllm.uni_elements(elements,images)
    out = repair_json(new_node_array)
    return out

def ele_set_update_rulebased(prior_ui_json, images, save_path=None):
    """
    prior_ui_json_path:  旧的 UI 元素 JSON 文件路径（内容是一个 list，每个元素是一个 dict）
    images:              [img0, img1] 两张 UI 截图，对应同一屏 UI 的“前后状态”
                         img0 / img1 是 OpenCV 读出来的 numpy 数组 (H, W, 3)
    save_path:           如果给出，则把更新后的 json 写回这个路径；否则不写文件
    return:              过滤后的新 json 列表（Python list）
    """

    if len(images) != 2:
        raise ValueError("images 必须包含两张图片：images[0], images[1]")

    img0= cv2.imread(images[0])
    img1= cv2.imread(images[1])

    # 2. 转灰度，做差分，得到变化的区域（一个或多个矩形框）
    gray0 = cv2.cvtColor(img0, cv2.COLOR_BGR2GRAY)
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)

    # 绝对差分
    diff = cv2.absdiff(gray0, gray1)

    # 阈值化：把差异比较明显的像素变成 255
    _, diff_bin = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

    # 形态学操作，适当扩展一下区域，把小块连在一起
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    diff_bin = cv2.dilate(diff_bin, kernel, iterations=2)
    diff_bin = cv2.erode(diff_bin, kernel, iterations=1)

    # 找轮廓，得到变化区域的 bounding box 列表
    contours, _ = cv2.findContours(diff_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    diff_regions = []  # 每个元素是 (x1, y1, x2, y2)
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        x1, y1 = x, y
        x2, y2 = x + w, y + h
        diff_regions.append((x1, y1, x2, y2))

    # 如果没有检测到变化区域，直接返回原 json
    if not diff_regions:
        if save_path is not None:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(prior_ui_json, f, ensure_ascii=False, indent=2)
        return prior_ui_json

    # 3. 定义一个函数判断一个元素的中心点是否落在任意变化区域中
    def is_in_diff_region(elem):
        # 有些数据里 boundLeft / boundRight 可能大小颠倒，这里做个标准化
        x1 = min(elem["boundLeft"], elem["boundRight"])
        x2 = max(elem["boundLeft"], elem["boundRight"])
        y1 = min(elem["boundTop"], elem["boundBottom"])
        y2 = max(elem["boundTop"], elem["boundBottom"])

        # 用元素中心点判断是否在 diff 区域内
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        for rx1, ry1, rx2, ry2 in diff_regions:
            if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                return True
        return False

    # 4. 过滤掉“在变化区域内”的元素
    new_ui_json = [elem for elem in prior_ui_json if not is_in_diff_region(elem)]

    # 5. 需要的话写回文件
    if save_path is not None:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(new_ui_json, f, ensure_ascii=False, indent=2)

    return new_ui_json

def smart_back(ui_json, image, dir_path):
    img = cv2.imread(image)

    #with open(ui_json_path, 'r', encoding='utf-8') as f:
    #    ui_json = json.load(f)

    #updated_json = ele_set_update_rulebased(ui_json, images)
    # 将处理后的 UI 元素 bounding box 绘制在 ui_image_after 上

    image_after_with_boxes, updated_json = draw_bounding_boxes(img, ui_json , color=(0, 0, 255), thickness=2)

    # 显示绘制后的图片
    #cv2.imshow("Updated UI with Bounding Boxes", image_after_with_boxes)
    #cv2.waitKey(0)
    #cv2.destroyAllWindows()
    new_image_after = os.path.join(dir_path,"back_from.jpg")
    cv2.imwrite(new_image_after, image_after_with_boxes)
    print(updated_json)

    _ , out = mllm.smart_back(updated_json,new_image_after)
    out = repair_json(out)
    bbx = json.loads(out)
    print("bbx",bbx)
    coordinate_x = (bbx["boundLeft"] + bbx["boundRight"])/2
    coordinate_y = (bbx["boundTop"] + bbx["boundBottom"])/2

    return coordinate_x,coordinate_y

def draw_bounding_boxes(image, ui_elements, color=(0, 0, 255), thickness=2): 
    """ 在 image 图像上绘制 ui_elements 的 bounding box

    参数:
    image: OpenCV 读取的图像（numpy 数组）
    ui_elements: UI 元素列表，每个元素包含 boundLeft, boundTop, boundRight, boundBottom 字段
    color: bounding box 的颜色，默认为绿色
    thickness: 矩形线条宽度，默认为2
    返回:
    绘制后的图像（原图被修改）
    """
    index = 0

    for item in ui_elements:
        item["index"] = index
        left = item.get("boundLeft", 0)
        top = item.get("boundTop", 0)
        right = item.get("boundRight", 0)
        bottom = item.get("boundBottom", 0)
        
        # 绘制矩形框
        cv2.rectangle(image, (left, top), (right, bottom), color, thickness)
        
        # 在框的左上角标记索引号码
        text = str(index)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        text_thickness = 2
        text_color = (255, 0, 0)  # 蓝色文字
        
        # 获取文字尺寸
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, text_thickness)
        
        # 计算文字位置（框的左上角稍微偏移）
        text_x = left + 5
        text_y = top + text_height + 5
        
        # 绘制文字背景（可选，提高可读性）
        cv2.rectangle(image, 
                    (text_x - 2, text_y - text_height - 2),
                    (text_x + text_width + 2, text_y + 2),
                    (255, 255, 255), -1)  # 白色背景
        
        # 绘制索引文字
        cv2.putText(image, text, (text_x, text_y), font, font_scale, text_color, text_thickness)
        
        index += 1
        
    return image,ui_elements

def image_to_vector(img_path):
    # 图像预处理
    preprocess = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # 加载图片，并确保图片是RGB格式
    img = Image.open(img_path).convert('RGB')
    img_tensor = preprocess(img)
    img_tensor = img_tensor.unsqueeze(0)  # 添加batch维度

    # 使用模型提取特征
    with torch.no_grad():
        features = model(img_tensor)

    # 返回展平的特征向量
    return features.flatten().numpy()

# 示例：将UI图像转换为向量
#ui_vector = image_to_vector('path_to_ui_image.jpg')
#print(ui_vector)

def cosine_similarity(vec1, vec2):
    """计算两个向量之间的余弦相似度"""
    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)
    return dot_product / (norm_vec1 * norm_vec2)

def find_most_similar_ui(input_features, database):
    """在数据库中找到最相似的UI界面"""
    max_similarity = -1
    most_similar_ui = None
    for ui in database:
        similarity = cosine_similarity(input_features, ui["features"])
        print(similarity)
        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_ui = ui

    return most_similar_ui, max_similarity

# 对于标注完的app页面数据，先生成pages.json
def generate_pages(package_name):
    # 构建目录路径
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'UIdata', package_name)

    # 读取 updated_visitList.json 文件
    visit_list_path = os.path.join(dir_path, 'updated_visitList.json')
    with open(visit_list_path, 'r') as visit_file:
        visit_list = json.load(visit_file)

    # 获取 visit_list 的长度
    visit_list_length = len(visit_list)

    # 初始化一个大列表来存储所有的 JSON 对象
    all_pages = []

    # 遍历 dir_path 下的所有文件
    for i in range(visit_list_length):
        filename = str(i)+"_Leaf.json"
        file_path = os.path.join(dir_path, filename)
        with open(file_path, 'r') as json_file:
            # 读取 JSON 文件并将其内容添加到 all_pages 列表中
            json_data = json.load(json_file)
            all_pages.append(json_data)  # 假设 json_data 是一个列表

    # 存储合并后的结果到 pages.json
    pages_file_path = os.path.join(dir_path, 'pages.json')
    with open(pages_file_path, 'w') as pages_file:
        json.dump(all_pages, pages_file, indent=4)  # 使用 indent=4 格式化输出
    print("pages length:", visit_list_length)  # 可选：返回 visit_list 的长度

# 对于移动端传递回来的screenList,给每一个屏幕以及每一个元素加上index number,并且移除不必要的element属性，缩短token, 对于new_screenList,保留每个UI text的embedding
def add_index_number_for_new_screenList(package_name):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'pages.json'), "r") as f:
        screenList = json.load(f)
    new_screenList = []
    for i in range(len(screenList)):
        brev_screen = []
        print(i)
        for j in range(len(screenList[i])):
            brev_element = {}
            brev_element["element_index_number"] = j
            try:
                brev_element["class"] = screenList[i][j]["class"]
                brev_element["text"] = screenList[i][j]["text"]
                _, element_embedding = UI_text_model.get_embedding(brev_element["text"])
                brev_element["element_embedding"] = element_embedding.tolist()

            except KeyError:
                print("no class")
            brev_screen.append(brev_element)
            #screenList[i][j]["element_index_number"] = j
        #brev_screen_str = str(brev_screen)
        #_, screen_embedding = UI_text_model.get_embedding(brev_screen_str)
        new_screenList.append({"screen_index_number":i, "UI_content":brev_screen})
    print(new_screenList)
    with open(os.path.join(dir_path, "new_screenList.json"), "w") as file:
        json.dump(new_screenList, file, indent=4)

def add_index_number_for_screenList(package_name):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'pages.json'), "r") as f:
        screenList = json.load(f)
    new_screenList = []
    for i in range(len(screenList)):
        brev_screen = []
        print(i)
        for j in range(len(screenList[i])):
            brev_element = {}
            brev_element["element_index_number"] = j
            try:
                brev_element["class"] = screenList[i][j]["class"]
                brev_element["text"] = screenList[i][j]["text"]
            except KeyError:
                print("no class")
            brev_screen.append(brev_element)
            #screenList[i][j]["element_index_number"] = j
        #brev_screen_str = str(brev_screen)
        #_, screen_embedding = UI_text_model.get_embedding(brev_screen_str)
        new_screenList.append({"screen_index_number":i, "UI_content":brev_screen})
    print(new_screenList)
    with open(os.path.join(dir_path, "screenList.json"), "w") as file:
        json.dump(new_screenList, file, indent=4)

# 创建function seek的数据集，用于微调或者few shot prompting
def create_function_seek_dataset(package_name,prompt,screen_index_number,element_index_number):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'new_screenList.json'), "r", encoding="utf-8") as f:
        screenList = json.load(f)
    if os.path.exists("function_seek_dataset.json"):
        with open("function_seek_dataset.json", "r") as f:
            app_set = json.load(f)
    else:
        app_set = []
    item = {}
    item["instruction"] = prompt
    item["input"] = json.dumps(screenList)
    item["output"] = json.dumps({"screen_index_number": screen_index_number, "element_index_number": element_index_number})
    app_set.append(item)
    with open("function_seek_dataset.json", "w") as file:
        json.dump(app_set, file, indent=4)
    return

def split_into_batches(data, batch_size=12):
    return [data[i:i+batch_size] for i in range(0, len(data), batch_size)]

def find_global_max_similarity(target_embedding, embedding_dict):
    """
    在嵌套字典结构中查找全局最大相似度

    参数：
    target_embedding: 目标embedding向量(np.ndarray)
    embedding_dict: 格式为{key: [embedding1, embedding2...]}的嵌套字典

    返回：
    (包含全局最大相似度的key, 该key下的子索引, 相似度分数)
    """
    global_max = -1
    result_key = None
    result_sub_idx = -1

    target = np.array(target_embedding)
    norm_target = np.linalg.norm(target)

    for key, embedding_list in embedding_dict.items():
        # 转换当前列表为numpy数组
        embeddings = np.array(embedding_list)

        # 批量计算余弦相似度
        dot_product = np.dot(embeddings, target)
        norm_embeddings = np.linalg.norm(embeddings, axis=1)
        similarities = dot_product / (norm_embeddings * norm_target)

        # 找当前列表的最大值
        current_max_idx = np.argmax(similarities)
        current_max = similarities[current_max_idx]

        # 更新全局最大值
        if current_max > global_max:
            global_max = current_max
            result_key = key
            result_sub_idx = current_max_idx

    return result_key, result_sub_idx, global_max

def get_matching_keys(target_embedding, embedding_dict, threshold):
    """
    获取所有相似度超过阈值的唯一key集合

    参数：
    target_embedding: 目标向量(np.ndarray)
    embedding_dict: {key: [embedding1, embedding2...]}格式的字典
    threshold: 相似度阈值(0-1)

    返回：
    set: 包含所有符合条件key的集合
    """
    matched_keys = set()
    target = np.array(target_embedding)
    norm_target = np.linalg.norm(target)

    for key, embedding_list in embedding_dict.items():
        embeddings = np.array(embedding_list)
        dot_products = np.dot(embeddings, target)
        norms = np.linalg.norm(embeddings, axis=1)
        similarities = dot_products / (norms * norm_target)

        if np.any(similarities >= threshold):
            matched_keys.add(key)

    return matched_keys

def get_top_matching_keys(target_embedding, embedding_dict,topN):
    """
    获取与目标向量相似度最高的前3个key

    参数：
    target_embedding: 目标向量(np.ndarray)
    embedding_dict: {key: [embedding1, embedding2...]}格式的字典

    计算：
    [(key, 最高相似度分数)...] (按分数降序，最多topN项)

    返回：
    set: 包含所有符合条件key的集合
    """
    matched_keys = set()
    top_keys = []
    target = np.array(target_embedding)
    norm_target = np.linalg.norm(target)

    for key, embedding_list in embedding_dict.items():
        embeddings = np.array(embedding_list)
        dot_products = np.dot(embeddings, target)
        norms = np.linalg.norm(embeddings, axis=1)
        similarities = dot_products / (norms * norm_target)
        max_sim = np.max(similarities)
        top_keys.append((key, max_sim))

    # 按相似度降序排序并取前3
    top_keys.sort(key=lambda x: -x[1])
    topN_keys = top_keys[:topN]
    for key in topN_keys:
        matched_keys.add(key[0])
    return matched_keys


def function_retrieve(package_name, prompt, thresholdORtopN):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'new_screenList.json'), "r", encoding="utf-8") as f:
        screenList = json.load(f)
    embedding_list = []
    _, prompt_embedding = UI_text_model.get_embedding(prompt)

    dict = {}
    for screen in screenList:
        screen_embeddings = []
        for element in screen["UI_content"]:
            try:
                screen_embeddings.append(element["element_embedding"])
            except KeyError:
                print("no class")
        dict[screen["screen_index_number"]] = screen_embeddings

    #result_key, result_sub_idx, global_max_similarity = find_global_max_similarity(prompt_embedding, dict)
    if thresholdORtopN<1:
        matched_keys = get_matching_keys(prompt_embedding, dict, thresholdORtopN)

    else:
        matched_keys = get_top_matching_keys(prompt_embedding, dict, thresholdORtopN)
    print("matches",matched_keys)
    #print("目标页面是：", result_key, "相似度为:", global_max_similarity)
    return matched_keys


def function_seek(package_name, prompt, candidate_screens):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'screenList.json'), "r", encoding="utf-8") as f:
        screenList = json.load(f)

    if os.path.exists("function_seek_dataset.json"):
        with open("function_seek_dataset.json", "r") as f:
            exemplars = json.load(f)
        final_batch = [screenList[key] for key in candidate_screens]
        _, output = UI_text_model.seek_function(final_batch, exemplars, prompt)
        print("function_seek output:", output)
        try:
            output = json.loads(output)
            print("function_seek output json:", output)
            isJSON = True
        except:
            print("not json")
            isJSON = False

        if isJSON:
            return int(output["screen_index_number"]), int(output["element_index_number"])
        else:
            return 0, 0
            #output = json.loads(output)
    else:
        print("please create function seek dataset")
    return


'''
def function_seek(package_name, prompt):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'new_screenList.json'), "r", encoding="utf-8") as f:
        screenList = json.load(f)

    if os.path.exists("function_seek_dataset.json"):
        with open("function_seek_dataset.json", "r") as f:
            exemplars = json.load(f)

        # 将数据分成小批次进行处理
        screen_batches = split_into_batches(screenList)

        # 用于存储所有批次的返回值
        all_screen_indices = []
        isJSON = False

        # 分批处理，每次只传递一部分数据
        for screen_batch in screen_batches:
            _, output = UI_text_model.seek_function(screen_batch, exemplars, prompt)
            print("function_seek batch output:", output)
            try:
                output = json.loads(output)
                print("function_seek batch output json:", output)
                isJSON = True
            except:
                print("not json")
                isJSON = False

            if isJSON == True:
                # 获取返回的screen_index_number并保存
                #screen_index = int(output.get("screen_index_number"))
                all_screen_indices.append(output)

        isJSON = False
        final_batch = [screenList[int(object.get("screen_index_number"))] for object in all_screen_indices]
        _, output = UI_text_model.seek_function(final_batch, exemplars, prompt)
        print("function_seek output:", output)
        try:
            output = json.loads(output)
            print("function_seek output json:", output)
            isJSON = True
        except:
            print("not json")
            isJSON = False

        if isJSON:
            return int(output["screen_index_number"]), int(output["element_index_number"])
        else:
            return int(all_screen_indices[0]["screen_index_number"]), int(all_screen_indices[0]["element_index_number"])
            #output = json.loads(output)
    else:
        print("please create function seek dataset")
    return
'''


def app_seeking(applist, prompt):
    _,app = UI_text_model.app_seek(applist, prompt)
    return app
def context_judge(current_screenshot, app):
    _,answer = UI_text_model.context_judge(current_screenshot, app)
    if answer == "Yes":
        return True
    else:
        return False

def legality_check(current_screenshot, intent,app_list):
    _, answer = mllm.desktop_check(intent, [current_screenshot])
    if answer == "Yes":
        #如果是桌面状态直接认为这是不合法的query
        return False,None
    else:
        #如果是app界面
        _, answer = mllm.out_of_domain_check(intent, [current_screenshot])
        if answer == "Yes":
            _, app = mllm.app_select(app_list, [current_screenshot])
            return True,app
        else:
            return False,None

def app_level_check(QA_summary, candidate_apps):
    app_list = candidate_apps.keys()
    _, apps = UI_text_model.app_select(app_list, QA_summary)
    _, app_conversation_answer = UI_text_model.app_conversation_back(QA_summary)
    print("apps", apps,"answer",app_conversation_answer)
    try:
        #apps = json.loads(apps)
        result = [item.strip() for item in apps.split(',')]
        print(result)
        apps = result
        print("app select output json:", apps)
        isJSON = True
    except:
        print("not json")
        isJSON = False
    if isJSON:
        app = None
        if len(apps) >1:
            isAppUnique = False
            answer = app_conversation_answer +"。"+"您希望使用哪个app呢？"
            for app in apps:
                answer = answer + candidate_apps[app][3]+"？"
        elif len(apps) == 1:
            isAppUnique = True
            app = apps[0]
            answer = "即将为您打开"+candidate_apps[app][3]
        else:
            isAppUnique = False
            answer = "对不起，做不了"
        return isAppUnique, answer, app
    else:
        return False, "您的表达不明确，请指出具体需要使用的app", None

def UI_level_response(QA_summary):
    _, answer = UI_text_model.conversation_back(QA_summary)
    return answer



'''
# 根据用户的prompt找到目标页面以及目标元素
def function_seek(package_name, prompt):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'new_screenList.json'), "r", encoding="utf-8") as f:
        screenList = json.load(f)
    if os.path.exists("function_seek_dataset.json"):
        with open("function_seek_dataset.json", "r") as f:
            exemplars = json.load(f)
        _, output = UI_text_model.seek_function(screenList,exemplars,prompt)
        output = json.loads(output)
        print("function_seek output:", output)
        return int(output["screen_index_number"]), int(output["element_index_number"])
    else:
        print("please create function seek dataset")
    return
'''

# 根据用户当前界面的截图判断是否访问过此界面，并且找到当前页面在utg中的位置,冻结的页面不参与匹配
def screenRelocation(package_name,current_screenshot):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),package_name)
    with open(os.path.join(dir_path, 'utg.json'), "r", encoding="utf-8") as f:
        utg = json.load(f)
    current_ui_vec = image_to_vector(current_screenshot)
    ui_vec_database = []
    for i in range(len(utg)):
        print(i)
        if utg[i][0]["screen"]==-1:
            print("frozen screen")
            continue
        scaned_screen = os.path.join(dir_path, str(i)+"_screenshot.jpg")
        temp_ui_vec = image_to_vector(scaned_screen)
        ui_vec_database.append({"id":i, "features": temp_ui_vec})
    most_similar_ui, max_similarity = find_most_similar_ui(current_ui_vec, ui_vec_database)
    print(most_similar_ui["id"], max_similarity)
    return most_similar_ui["id"], max_similarity


def find_path(package_name, current_screen, target_screen):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'utg.json'), "r", encoding="utf-8") as f:
        utg = json.load(f)
    screens = utg

    """
    screens: 二维列表，screens[i] 是第 i 个 screen 的可跳转列表
             每个可跳转由一个 dict 表示: {"element": E, "screen": S}
    current_screen: 起始页面的序号
    target_screen: 目标页面的序号

    返回值:
      若有路径, 返回形如:
         [
           {"screen": x0, "element": e0},
           {"screen": x1, "element": e1},
           ...
         ]
      其中 x0, x1,... 是页面的序号, e0, e1,... 是在该页面上点击的元素序号
      若无可达路径, 返回 None
    """
    # 如果起始页面就等于目标页面，通常可视为不需要点击就已在目标页面
    if current_screen == target_screen:
        #return [{"screen": current_screen, "element": -1}]  # 或者返回 []
        return []

    # 用于记录已经访问过的页面，避免死循环
    visited = set([current_screen])
    # 队列中每个元素: (当前screen, 路径)
    # 路径是一个列表, 保存了从起始screen到达当前screen所经过的[screen, element]信息
    queue = deque()
    queue.append((current_screen, []))

    print("visited", visited)
    while queue:
        screen_now, path = queue.popleft()
        # 遍历该页面所有可点击的元素及其跳转
        for edge in screens[screen_now]:
            element = edge["element"]
            next_screen = edge["screen"]

            if next_screen not in visited:
                # 在原 path 上追加当前这一步 (screen_now 上点击了 element)
                new_path = path + [{"screen": screen_now, "element": element}]

                # 如果已经到达目标页面，则返回整条路径
                if next_screen == target_screen:
                    return new_path

                visited.add(next_screen)
                queue.append((next_screen, new_path))

    # 如果 BFS 无法找到目标页面，则返回 None
    print("没有找到可行路径")
    return []

def get_next_screen(package_name, current_screen, element_to_click):
    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    with open(os.path.join(dir_path, 'utg.json'), "r", encoding="utf-8") as f:
        utg = json.load(f)
    screens = utg
    """
    在 current_screen 页面，点击 element_to_click 之后返回下一页面序号。
    如果找不到相应的 element，则返回 None (或抛出异常)
    """
    if current_screen < 0 or current_screen >= len(screens):
        return None

    for edge in screens[current_screen]:
        if edge["element"] == element_to_click and edge["screen"]!=current_screen:
            return edge["screen"]

    # 若遍历后没找到，就说明这个页面没有存储该 element 所链接的页面信息
    return None

def service_explanation(screenshot_path, user_intent, round):
    """
    基于用户的问题对服务相关的所有UI元素进行解释和框选
    :param screenshot_path: 目标页面的图像
    :param user_intent: 用户需求
    :return:
    """
    # 对给定的UI图像做set of mark
    output_name = "user_track/" +str(round)
    img_output_path, metadata_output_path = set_of_marks_omniparser(screenshot_path, output_name)

    status, rsp = mllm.prompot_gpt4o_for_all_related_elements(user_intent, [img_output_path], metadata_output_path)
    rsp = json.loads(rsp)
    print(rsp)

    return rsp

def related_step_identification(screenshot_path, screen_brev , user_intent):
    """
    生成对于当前页面主要功能的解释
    判断当前页面是否未能完成与用户意图相关的操作，如果仍需要下一步操作，判断move到下一步的相关element 并返回 element_to_next

    - element_explanation: dict
    - element_to_next: int, 如果下一步还需要点击/输入的element的序号
    """
    screen_brev = json.dumps(screen_brev)
    _,screen_function_explanation = UI_text_model.screen_function_explanation(screenshot_path,user_intent)

    _, judgement = UI_text_model.last_step_identification(screenshot_path,user_intent)
    #judgement = bool(judgement)
    print(judgement, isinstance(judgement,bool))

    if judgement=="False":
        if os.path.exists("function_seek_dataset.json"):
            with open("function_seek_dataset.json", "r") as f:
                exemplars = json.load(f)
        else:
            print("please create function seek dataset")
        _,element_to_next = UI_text_model.single_screen_function_identification(screenshot_path,screen_brev,exemplars,user_intent)
        element_to_next = json.loads(element_to_next)
        return screen_function_explanation, element_to_next["element_index_number"]
    else:
        print("end service related action explain")
        return screen_function_explanation, -1



if __name__ == '__main__':
    '''
    package_name = "ctrip.android.view"
    #package_name = "ctrip.android.view"
    #package_name = 'com.lucky.luckyclient'
    #generate_pages(package_name)
    #dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'UIdata',package_name)
    #with open(os.path.join(dir_path, 'pages.json'), 'r') as f:
    #    pages_metadata = json.load(f)
    add_index_number_for_screenList(package_name)
    add_index_number_for_new_screenList(package_name)
    '''

    #instruction = "我想给我的飞机票申请报销"
    #screen_index_number = 14
    #element_index_number = 201
    #instruction = "我想选择飞机上的座位"
    #screen_index_number = 4
    #element_index_number = 49
    #create_function_seek_dataset(package_name,instruction,screen_index_number,element_index_number)

    #user_intent = "我要用携程app买郑州飞长春的机票" # I want to select a seat on the flight
    #screen_index_number = screen_retrieve(package_name, user_intent)

    #matched_keys = function_retrieve(package_name, user_intent, 0.85)

    '''
    start_time = time.time()
    user_intent = "我要找客服" # I want to select a seat on the flight
    with open(os.path.join(dir_path, 'new_screenList.json'), "r", encoding="utf-8") as f:
        screenList = json.load(f)
    screen_index_number, element_index_number = function_seek(package_name, user_intent)
    
    #screen_index_number = 14
    #element_index_number = 201
    
    current_screenshot = os.path.join(dir_path, "0_screenshot.jpg")
    current_screen_index, _ = screenRelocation(package_name,current_screenshot)
    path = find_path(package_name, current_screen_index, screen_index_number)
    print(path)
    #path.append({"screen": screen_index_number, "element": element_index_number})

    service_screen_index_number = screen_index_number
    service_screen_path = []
    #service_screen_index_number = get_next_screen(package_name, screen_index_number, element_index_number)
    service_screenshot = os.path.join(dir_path, str(service_screen_index_number)+"_screenshot.jpg")
    instruction, element_to_next = related_step_identification(service_screenshot, screenList[service_screen_index_number], user_intent)
    service_screen_path.append({"screen": service_screen_index_number, "element_explanation":instruction ,"element": element_to_next})
    while element_to_next>0:
        service_screen_index_number = get_next_screen(package_name, service_screen_index_number, element_to_next)
        print(service_screen_index_number)
        if service_screen_index_number==None:
            break
        else:
            service_screenshot = os.path.join(dir_path, str(service_screen_index_number)+"_screenshot.jpg")
            instruction, element_to_next = related_step_identification(service_screenshot, screenList[service_screen_index_number], user_intent)
            service_screen_path.append({"screen": service_screen_index_number, "element_explanation":instruction ,"element": element_to_next})

    print("navigational metadata:", path)
    print("service metadata:", service_screen_path)
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"程序运行时间: {execution_time:.4f} 秒")

    final_tutorial = generate_tutorial_images(dir_path, path, service_screen_path, pages_metadata, padding=50)
    '''
    '''
    
    generateStepPreview(
        before_img_path="before.png",
        after_img_path="after.png",
        click_position=(300, 500),  # 点击坐标
        finger_icon_path="finger.png",  # 手指图标（建议使用透明PNG）
        output_gif_path="interactive_transition.gif",
        duration=50,  # 每帧50ms（20fps）
        total_frames=30,
        click_duration_frames=8
    )
    '''
    #screenshot_path = "set_of_mark/user_track/0.jpg"
    #user_intent = "我要买去广西的机票"
    #service_explanation(screenshot_path, user_intent, 1)

    dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","appData", "ctrip.english")
    images = ["/Users/xiaozhuhu/Desktop/AppFlating_online_UTG_annotate_tool/static/appData/ctrip.english/1_screenshot.jpg","/Users/xiaozhuhu/Desktop/AppFlating_online_UTG_annotate_tool/static/appData/ctrip.english/3_screenshot.jpg"]
    image_after = cv2.imread(images[1])
    
    ui_json_path = "/Users/xiaozhuhu/Desktop/AppFlating_online_UTG_annotate_tool/static/appData/ctrip.english/3_VH.json"
    
    with open(ui_json_path, 'r', encoding='utf-8') as f:
        ui_json = json.load(f)

    #updated_json = ele_set_update_rulebased(ui_json, images)
    # 将处理后的 UI 元素 bounding box 绘制在 ui_image_after 上

    image_after_with_boxes, updated_json = draw_bounding_boxes(image_after, ui_json , color=(0, 255, 0), thickness=2)

    # 显示绘制后的图片
    #cv2.imshow("Updated UI with Bounding Boxes", image_after_with_boxes)
    #cv2.waitKey(0)
    #cv2.destroyAllWindows()
    #print(updated_json)

    coord = smart_back(ui_json_path, images, dir_path)
    print(coord)

    



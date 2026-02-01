import os
import base64
from datetime import datetime
import paho.mqtt.client as mqtt
from utils import *
import threading
import time
from utils import *
from PIL import Image
import io
import time
import cv2 as cv
import json

# 声明 MQTT 客户端为global
global client

# 设置全局变量判断当前处于提问还是追问
global isInitialQuery
isInitialQuery = True
global previewQuery
previewQuery = {"preStep":None,"postStep":None,"x":None,"y":None}

# 当连接到 MQTT 代理时的回调函数
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully!")
        # 连接成功后订阅多个主题
        client.subscribe("fileTopic",qos=1)
        client.subscribe("tempScreenTopic",qos=1)
        client.subscribe("smartBackTopic",qos=1)
        client.subscribe("screenshotTopic",qos=1)
        client.subscribe("query",qos=1)
        client.subscribe("previewVM",qos=1)
        client.subscribe("previewAgent",qos=1)
        client.subscribe("stepOperateAgent",qos=1)
        #client.subscribe("imageTopic",qos=1)
        client.subscribe("textTopic")
    else:
        print(f"Failed to connect, return code {rc}")


# 当从 MQTT 主题收到消息时的回调函数
def on_message(client, userdata, msg):
    global isInitialQuery
    global timer
    global curScreen
    global previewQuery
    try:
        if msg.topic == "textTopic":
            handle_text(msg)
            call_back_data = {"screenNum": 1, "isSame": True}
            call_back_message = json.dumps(call_back_data)

            if(client.publish("myCloud", call_back_message)):
                print("回传成功")
            else:
                print("回传失败")
        else:
            #无论来自哪个主题，都先解析成json
            query_data = json.loads(msg.payload.decode())
            # 检查消息是来自哪个主题
            if msg.topic == "fileTopic":
                handle_file(query_data)
                #call_back_data = {"fileArrived": "success"}
                #call_back_message = json.dumps(call_back_data)
                #if(client.publish("fileCallback", call_back_message)):
                #    print("回传成功")
                #else:
                #    print("回传失败")

            if msg.topic == "screenshotTopic":
                # 创建文件保存路径
                dir_path, image_path, file_name, ui_elements = handle_Screen(query_data)
                print("save screenshot to",image_path)
                call_back_data = {"screenNum": 0, "isSame": False}
                call_back_message = json.dumps(call_back_data)
                if(client.publish("myCloud", call_back_message)):
                    print("回传成功")
                else:
                    print("回传失败")

            if msg.topic == "smartBackTopic":
                print("receive smartBackTopic")
                dir_path,image_path,file_name,ui_elements = handle_Screen(query_data,isTemp=True)
                coord_x,coord_y = smart_back(ui_elements, image_path, dir_path)
                
                call_back_data = {"coordinate_x": coord_x, "coordinate_y": coord_y}
                call_back_message = json.dumps(call_back_data)
                print("call_back_message")

                if(client.publish("BackTopic", call_back_message)):
                    # 获取当前时间戳
                    current_time = time.time()
                    # 打印当前时间戳
                    print("Current timestamp:", current_time)
                    # 转换为可读格式
                    readable_time = time.ctime(current_time)
                    print("Current time:", readable_time)
                    print("回传成功")
                else:
                    print("回传失败")
                

            if msg.topic == "tempScreenTopic":
                # 解析JSON字符串
                #query_data = json.loads(msg.payload.decode())
                #print(query_data)
                dir_path, image_path, file_name, ui_elements = handle_Screen(query_data,isTemp=True)
                #print("handled temp screen dir path",dir_path)
                #print("handled temp screen image_path",image_path)
                #print("handled temp screen file_name",file_name)
                #print("handled temp screen ui_elements",ui_elements)
                
                screenNum, similarity = screenRelocation(dir_path, image_path)
                print("screenNum", screenNum)
                print("similarity", similarity)
                if similarity<=0.8:
                    with Image.open(image_path) as img:
                        img.save(os.path.join(dir_path,file_name))
                    isSame = False
                    new_node_array = [] #设为none或者空列表都可以，反正当isSame和page_freeze都为False的时候，直接认定它是新页面而且需要保留，那么就不会管这个new_node_array了，直接用移动端已经抓好的就行,如果page_freeze为True则正好取new_node_array为空列表
                    #screenNum = -1 #加不加这个都无所谓反正这个screenNum也对移动端没有任何影响
                    isDeserved, resp = worthness_judge(image_path) #价值判断，human evaluator介入的touch point
                    print("touch point: worthness judgement:", isDeserved)
                    #cv show image
                    #input(Y or N)
                    #save AI judgement and human judgement
                    result = cv.imread(image_path)
                    cv.imshow("worthness judgement", result)
                    cv.waitKey(0)
                    cv.destroyAllWindows()
                    print("请判断当前页面是否值得AI助手深入探索其功能")
                    human_judgement = ""
                    input(human_judgement)
                    if human_judgement == "Y" or human_judgement == "y":
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
                    if not os.path.exists(os.path.join(dir_path,dir_name)):
                        os.makedirs(os.path.join(dir_path,dir_name))
                        print("文件夹已创建<0.8")
                    else:
                        print("文件夹已存在<0.8")
                    cv.imwrite(os.path.join(dir_path,dir_name,f_name+".jpg"), result)
                    with open(os.path.join(dir_path,dir_name,f_name+".json"), "w", encoding="utf-8") as f:
                        json.dump({f_name:resp}, f, ensure_ascii=False, indent=2)
                    
                elif similarity>0.99:
                    images = [os.path.join(dir_path, str(screenNum)+"_screenshot.jpg"),image_path]
                    prior_ui_json_path = os.path.join(dir_path,str(screenNum)+"_Leaf.json")
                    with open(prior_ui_json_path, "r", encoding="utf-8") as f:
                            prior_ui_json = json.load(f)
                    if len(prior_ui_json) > 0: #代表此页面是有价值的
                        new_node_array = ele_set_update_rulebased(prior_ui_json, images, save_path=prior_ui_json_path)
                        print("AI generate new node array (json of a UI screen)", new_node_array)
                        isSame = True
                        page_freeze = False
                    else:
                        new_node_array = []
                        print("new node array is none for the same but not worth ui screen", new_node_array)
                        isSame = True
                        page_freeze = True #如果相同页面是不值得探索的，把new_node_array设为空然后往回传就可，follow相同的规则是没问题的
                else:
                    images = [os.path.join(dir_path, str(screenNum)+"_screenshot.jpg"),image_path]
                    isSame,resp = same_screen_discriminator(images) #相同界面判断，human evaluator介入的touch point
                    print("touch point: same screen judgement:", isSame)
                    #cv show two images
                    #input(Y or N)
                    #save AI judgement and human judgement
                    im1 = cv.imread(images[0])
                    im2 = cv.imread(images[1])

                    # 水平拼接图像
                    result = np.hstack((im1, im2))

                    cv.imshow("same screen judgement", result)
                    cv.waitKey(0)
                    cv.destroyAllWindows()
                    print("请判断当前的两个页面是否为相同页面")
                    human_judgement = ""
                    input(human_judgement)
                    if human_judgement == "Y" or human_judgement == "y":
                        if isSame:
                            dir_name = "same_all_TP"
                        else:
                            dir_name = "same_human_FN"
                        isSame = True
                    else:
                        if isSame:
                            dir_name = "different_human_FP"
                        else:
                            dir_name = "different_all_TN"
                        isSame = False
                    timestamp = int(time.time())
                    f_name = f"concatenated_{timestamp}"
                    if not os.path.exists(os.path.join(dir_path,dir_name)):
                        os.makedirs(os.path.join(dir_path,dir_name))
                        print("文件夹已创建issame")
                    else:
                        print("文件夹已存在issame")
                    cv.imwrite(os.path.join(dir_path,dir_name,f_name+".jpg"), result)
                    with open(os.path.join(dir_path,dir_name,f_name+".json"), "w", encoding="utf-8") as f:
                        json.dump({f_name:resp}, f, ensure_ascii=False, indent=2)

                    prior_ui_json_path = os.path.join(dir_path,str(screenNum)+"_Leaf.json")
                    if isSame:
                        #new_node_array = ele_set_update(ui_elements, prior_ui_json_path, images) #需要有一种方法来处理同一个页面不同variation下UI element在位置上的动态调整，比如把两个json里面共同的元素识别出来，然后按照旧的顺序记录UI element把新的位置也加进去，确保静态页面上的UI是对的，然后每个UI对应的下一个页面也是对的。对于没有static的情况先都转成static，然后把最新的位置写为boundTop这些。对于有static的情况，保留static，更新bound。
                        with open(prior_ui_json_path, "r", encoding="utf-8") as f:
                            prior_ui_json = json.load(f)
                        if len(prior_ui_json) > 0: #代表此页面是有价值的
                            new_node_array = ele_set_update_rulebased(prior_ui_json, images, save_path=prior_ui_json_path)
                            print("AI generate new node array (json of a UI screen)", new_node_array)
                            isSame = True
                            page_freeze = False
                        else:
                            new_node_array = []
                            print("new node array is none for the same but not worth ui screen", new_node_array)
                            isSame = True
                            page_freeze = True #如果相同页面是不值得探索的，把new_node_array设为空然后往回传就可，follow相同的规则是没问题的

                    else:
                        #确认是新页面
                        #page_freeze = double_page_judgement() #这里我们暂时先不做第二次价值判断，也就是说如果第一次价值判断这个页面是值得探索的，那么后续任何与它相似但是不同的页面我们不再去做二轮筛选，以确保相似但不同fragment的那种情况不被筛掉
                        with Image.open(image_path) as img:
                            img.save(os.path.join(dir_path,file_name))
                        isSame = False
                        new_node_array = [] #设为none或者空列表都可以，反正当isSame和page_freeze都为False的时候，直接认定它是新页面而且需要保留，那么就不会管这个new_node_array了，直接用移动端已经抓好的就行

                        isDeserved, resp = worthness_judge(image_path) #价值判断，human evaluator介入的touch point
                        print("touch point: worthness judgement:", isDeserved)
                        #cv show image
                        #input(Y or N)
                        #save AI judgement and human judgement
                        result = cv.imread(image_path)
                        cv.imshow("worthness judgement", result)
                        cv.waitKey(0)
                        cv.destroyAllWindows()
                        print("请判断当前页面是否值得AI助手深入探索其功能")
                        human_judgement = ""
                        input(human_judgement)
                        if human_judgement == "Y" or human_judgement == "y":
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
                    
                        if not os.path.exists(os.path.join(dir_path,dir_name)):
                            os.makedirs(os.path.join(dir_path,dir_name))
                            print("文件夹已创建not_same_worthness")
                        else:
                            print("文件夹已存在not_same_worthness")

                        cv.imwrite(os.path.join(dir_path,dir_name,f_name+".jpg"), result)
                        with open(os.path.join(dir_path,dir_name,f_name+".json"), "w", encoding="utf-8") as f:
                            json.dump({f_name:resp}, f, ensure_ascii=False, indent=2)
                        
                #else:
                #    with Image.open(image_path) as img:
                #        img.save(os.path.join(dir_path,file_name))
                #    page_freeze = True
                #    screenNum = -1
                #    isSame = False
                #    new_node_array = []

                call_back_data = {"screenNum": screenNum, "isSame": isSame, "page_freeze": page_freeze, "new_node_array": new_node_array}
                call_back_message = json.dumps(call_back_data)
                '''
                info = client.publish("myCloud", call_back_message, qos=1)
                print("smartBack publish mid:", info.mid)
                info.wait_for_publish()
                print("smartBack publish completed, is_published:", info.is_published())
                '''
                
                if(client.publish("myCloud", call_back_message)):
                    # 获取当前时间戳
                    current_time = time.time()
                    # 打印当前时间戳
                    print("Current timestamp:", current_time)
                    # 转换为可读格式
                    readable_time = time.ctime(current_time)
                    print("Current time:", readable_time)
                    print("回传成功")
                else:
                    print("回传失败")
                

            if msg.topic == "query":
                # 解析JSON字符串
                image_path = None
                question = None
                query_data = json.loads(msg.payload.decode())
                #print(query_data)

                # 处理健值对
                for key, value in query_data.items():
                    if key == "image":
                        image_path = handle_query_image(value)
                    elif key == "question":
                        question = handle_text(value)
                print(image_path, question)

                position, instruction = generate_navigation_box_with_GPT(image_path, question)
                print("position", position)
                print("instruction", instruction)

                # position = {'column_min': 599, 'row_min': 1134, 'column_max': 790, 'row_max': 1198, 'text': 'Text displaying the word "Booking" in bold font.', 'id': 7}
                # instruction = "The text \"Booking\" in bold font suggests a feature related to scheduling or reserving, which is relevant for booking a basketball time slot."
                #position = {'column_min': 599, 'row_min': 1133, 'column_max': 792, 'row_max': 1200, 'text': 'Text displaying the word "Booking" in bold font.', 'id': 3}
                #instruction = "任务是预订一个乒乓球桌，而“预订”文本暗示了与进行预订或预约相关的功能。链接UI元素是预订，ID是3。"
                #call_back_data = {"package": "-1", "start_cls": "-1","position": position, "instruction": instruction}
                call_back_data = {"position": position, "instruction": instruction}
                call_back_message = json.dumps(call_back_data)

                if client.publish("myCloud", call_back_message):
                    print("回传成功")
                else:
                    print("回传失败")

    except Exception as e:
        print(f"Failed to process the message: {e}")

def resize_image(input_path, output_path):
    # 打开图像
    with Image.open(input_path) as img:
        # 获取原始尺寸
        original_width, original_height = img.size
        # 计算新尺寸
        new_width = original_width // 4
        new_height = original_height // 4
        # 调整图像大小
        resized_img = img.resize((new_width, new_height))
        # 保存调整后的图像
        resized_img.save(output_path)

def compress_and_encode_image(file_path, output_format='PNG', quality=50):
    # 打开图像
    with Image.open(file_path) as img:
        # 创建一个字节流来保存压缩后的图像
        buffer = io.BytesIO()
        # 保存图像到字节流中，并进行压缩
        img.save(buffer, format=output_format, quality=quality)
        # 获取字节流的字节数据
        byte_data = buffer.getvalue()
        # 对字节数据进行Base64编码
        encoded_data = base64.b64encode(byte_data).decode('utf-8')
        return encoded_data


# 处理图片消息的函数
def handle_query_image(msg):
    try:
        # 创建图片保存路径
        image_folder = "image"
        if not os.path.exists(image_folder):
            os.makedirs(image_folder)

        # 获取当前时间戳作为文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        image_path = os.path.join(image_folder, f"{timestamp}.jpg")

        # 将 payload 转换为字符串
        #message_payload = msg.payload.decode()
        message_payload = msg

        transfer_base64_to_image(message_payload, image_path)

        return image_path
    except Exception as e:
        print(f"Failed to process the image: {e}")
        return None

# 处理文件消息的函数
def handle_file(data):
    try:
        # 获取文件名,应用包名和文件的 base64 数据
        file_name = data.get("fileName")
        package_name = data.get("packageName")
        base64_data = data.get("base64")
        dir_path = os.path.join(os.getcwd(),'static','appData', package_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        if file_name and base64_data:
            # 完整的文件保存路径
            file_path = os.path.join(dir_path, file_name)
            # 解码 base64 数据
            file_content = base64.b64decode(base64_data)
            # 将文件数据写入文件
            with open(file_path, "wb") as file_obj:
                file_obj.write(file_content)
            print(f"File saved to {file_path}")
        else:
            print("Invalid file data format. Missing 'fileName' or 'base64'.")
    except Exception as e:
        print(f"Failed to process the file: {e}")

# 处理文字消息的函数
def handle_text(msg):
    try:
        # 直接打印收到的文字消息
        #text_message = msg.payload.decode()
        text_message = msg
        print(f"Received text: {text_message}")

        return text_message
    except Exception as e:
        print(f"Failed to process the text message: {e}")
        return "error"

def transfer_base64_to_image(msg,image_path):
    # 检查并移除 `data:image/jpeg;base64,` 前缀
    if msg.startswith("data:image/jpeg;base64,"):
        message_payload = msg.replace("data:image/jpeg;base64,", "")

    # 解码 base64 数据
    image_data = base64.b64decode(message_payload)

    # 将图片数据写入文件
    with open(image_path, "wb") as image_file:
        image_file.write(image_data)

    print(f"Image saved to {image_path}")

def handle_back_json(data):
    try:
        # 获取文件名,应用包名和文件的 base64 数据
        prior_index = data.get("prior")
        package_name = data.get("packageName")
        current_index = data.get("current")
        print("prior screen", prior_index, "current_index", current_index)

        dir_path = os.path.join(os.getcwd(),'static','appData', package_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        prior_image_path = os.path.join(dir_path, str(prior_index)+"_screenshot.jpg")
        current_image_path = os.path.join(dir_path, str(current_index)+"_screenshot.jpg")
        current_json_path = os.path.join(dir_path, str(current_index)+"_VH.json")
        return dir_path,prior_image_path,current_image_path,current_json_path
    except Exception as e:
        print(f"Failed to process the image: {e}")
        return None,None


def handle_Screen(data,isTemp=False):
    try:
        # 获取文件名,应用包名和文件的 base64 数据
        file_name = data.get("text")
        package_name = data.get("packageName")
        base64_data = data.get("image")
        node_array = data.get("nodeArray")
        ui_elements = json.loads(node_array)

        dir_path = os.path.join(os.getcwd(),'static','appData', package_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        if isTemp:
            image_path = os.path.join(dir_path, "tempScreen.jpg")
        else:
            image_path = os.path.join(dir_path, file_name)
        transfer_base64_to_image(base64_data, image_path)
        return dir_path,image_path,file_name,ui_elements
    except Exception as e:
        print(f"Failed to process the image: {e}")
        return None,None

def run_mqtt_service():
    #add_index_number_for_screenList("ctrip.android.view")
    #add_index_number_for_screenList("com.openrice.android")
    client = mqtt.Client()
    # 设置连接和消息回调
    # 设置账号和密码（请将以下内容替换为实际的账号和密码）
    #username = "admin"
    #password = "admin"
    #client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message
    # 连接到 MQTT 代理（修改为你的代理地址和端口）
    #client.connect("", 1883, 60)
    client.connect("", 1883, 60)

    # # 开始循环，处理接收的消息
    client.loop_forever()


# create a new thread for the MQTT service
mqtt_thread = threading.Thread(target=run_mqtt_service)
# start the MQTT thread

mqtt_thread.start()

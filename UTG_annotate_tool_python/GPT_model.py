from openai import AzureOpenAI
import base64
from colorama import Fore, Style
import os
import yaml
import json
import requests

import re
from abc import abstractmethod
from typing import List
from http import HTTPStatus
import base64
from colorama import Fore, Style
import requests
import os
import json
import numpy as np
import cv2 as cv
import pandas as pd

'''
UI_image_model_system_prompt = "You are an ordinary smartphone user who can understand the transition logic between consecutive GUI screens. You will be given a pair of consecutive smartphone GUI screens, you need to identify the index number of the UI element that link the given UI screen to the target UI screen describe in texts. If you fail to do this, also explain your reason."
user_prompt = "Please describe how to transit from the prior UI screen to the later UI screen. You need to identify the index of the UI element that link the prior UI screen to the next UI screen"
#example_images_all_elements = [{"image": "set_of_mark/flight.jpg", "question": "我要买去广西的机票", "response": "{\"ids\":[3,12,19,39,40,42,44], \"explanation\":\"在此页面，您可以选择购买单程、双程、或多程的机票，选择出发地和目的地并通过点击查询来查询票价\"}"},
#                               {"image": "set_of_mark/coffee.jpg", "question": "我要喝咖啡", "response": "{\"ids\":[10，26], \"explanation\":\"在此页面，您可以选择咖啡的品类并且点击商品的名称来查看具体信息\"}"},
#                               {"image": "set_of_mark/cancel_flight.jpg", "question": "这个机票可以退吗", "response": "{\"ids\":[5,16], \"explanation\":\"您如果需要退票，可以点击退改签或者我要退票以查询相关规定\"}"}
#                               ]
example_images_all_elements = [{"image": "set_of_mark/flight.jpg", "question": "我要买去广西的机票", "response": "[{\"id\":3,\"explanation\":\"点击此处可购买单程票\"}, {\"id\":19,\"explanation\":\"点击此处可购买往返票\"}, {\"id\":44,\"explanation\":\"点击此处可选择出发地\"}, {\"id\":39,\"explanation\":\"点击此处可选择目的地\"}]"},
                              {"image": "set_of_mark/coffee.jpg", "question": "我要喝咖啡", "response": "[{\"ids\":10, \"explanation\":\"您可以在左侧列表选择咖啡品类，例如点击此处选择美式家族\"}, {\"ids\":26, \"explanation\":\"您可以在右侧列表选择具体商品，例如点击此处选择小话梅拿铁\"}]"},
                              {"image": "set_of_mark/cancel_flight.jpg", "question": "这个机票可以退吗", "response": "[{\"ids\":5, \"explanation\":\"您可以点击此处我要退票按钮来完成退票操作\"},{\"ids\":16, \"explanation\":\"您可以点击此处来查看退改签相关规定\"}]"}
                              ]

example_pairs_image = [
    {"prior": "set_of_marks_redbound_double_ori/2before.jpg", "next": "set_of_marks_redbound_double_ori/2after.jpg"},
    {"prior": "set_of_marks_redbound_double_ori/9before.jpg", "next": "set_of_marks_redbound_double_ori/9after.jpg"},
    {"prior": "set_of_marks_redbound_double_ori/30before.jpg", "next": "set_of_marks_redbound_double_ori/30after.jpg"},
    {"prior": "set_of_marks_redbound_double_ori/91before.jpg", "next": "set_of_marks_redbound_double_ori/91after.jpg"},
    {"prior": "set_of_marks_redbound_double_ori/47before.jpg", "next": "set_of_marks_redbound_double_ori/47after.jpg"}]

example_without_knowledge_response_image= [
    "8. \n On the target screen, the icon \'Plans\' located in the bottom nav bar is highlighted \n The link UI element is the \'Plans\' icon, the index is No.8",
    "2. \n The target screen appears to be displaying a passage from the Bible, which suggests clicking on the call-to-action on the first screen. \n The link UI element is the \'call-to-action\' button in the middle screen, the index is No. 2",
    "None. \n The prior screen and the next screen are of large visual difference. \n No link UI",
    "1. \n The target screen is the home page so I will tap the \'back\' icon to get back. \n The link UI element is the \'back\' icon, the index is No.1",
    "2. \n The target screen list many online shops, so I will tap the \'Purchases\' icon to transit to that screen. \n The link UI element is the \'Purchases\' item, the index is No.2"]

with open("UILinkII_test.json", "r", encoding="utf-8") as f:
    testset = json.load(f)
example_pairs = [testset[88],testset[95],testset[112],testset[43]]
example_without_knowledge_response = [
    "id:8. On the target screen, the icon \'Plans\' located in the bottom nav bar is highlighted \n The link UI element is the \'Plans\' icon, the id is 8",
    "id:2. The target screen appears to be displaying a passage from the Bible, which suggests clicking on the call-to-action on the first screen. \n The link UI element is the \'call-to-action\' button in the middle screen, the id is 2",
    "id:None. The prior screen and the next screen are of large visual difference. \n No link UI",
    "id:1. The target screen is the home page so I will tap the \'back\' icon to get back. \n The link UI element is the \'back\' icon, the id is 1"]
'''

def load_config(config_path="config.yaml"):
    configs = dict(os.environ)
    with open(config_path, "r") as file:
        yaml_data = yaml.safe_load(file)
    configs.update(yaml_data)
    return configs

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def print_with_color(text: str, color=""):
    if color == "red":
        print(Fore.RED + text)
    elif color == "green":
        print(Fore.GREEN + text)
    elif color == "yellow":
        print(Fore.YELLOW + text)
    elif color == "blue":
        print(Fore.BLUE + text)
    elif color == "magenta":
        print(Fore.MAGENTA + text)
    elif color == "cyan":
        print(Fore.CYAN + text)
    elif color == "white":
        print(Fore.WHITE + text)
    elif color == "black":
        print(Fore.BLACK + text)
    else:
        print(text)
    print(Style.RESET_ALL)

class OpenAIModel:
    def __init__(self, model, temperature, max_tokens):
        self.client = AzureOpenAI(
            api_key="",
            api_version="",
            azure_endpoint=""
        )
        self.model = model
        self.system_prompt = ""
        self.temperature = temperature
        self.max_tokens = max_tokens

    def few_shot_prompot_gpt4o_response(self, prompt, images):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]

        img1 = encode_image(images[0])
        img2 = encode_image(images[1])
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img1}"
            }
        })
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img2}"
            }
        })

        shot1 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img1 = encode_image(example_pairs_image[0]['prior'])
        base64_img2 = encode_image(example_pairs_image[0]['next'])
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        response1 = example_without_knowledge_response_image[0]

        shot2 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img3 = encode_image(example_pairs_image[1]["prior"])
        base64_img4 = encode_image(example_pairs_image[1]["next"])
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img3}"
            }
        })
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img4}"
            }
        })
        response2 = example_without_knowledge_response_image[1]

        shot3 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img5 = encode_image(example_pairs_image[2]["prior"])
        base64_img6 = encode_image(example_pairs_image[2]["next"])
        shot3.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img5}"
            }
        })
        shot3.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img6}"
            }
        })
        response3 = example_without_knowledge_response_image[2]

        shot4 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img7 = encode_image(example_pairs_image[3]["prior"])
        base64_img8 = encode_image(example_pairs_image[3]["next"])
        shot4.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img7}"
            }
        })
        shot4.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img8}"
            }
        })
        response4 = example_without_knowledge_response_image[3]

        shot5 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img9 = encode_image(example_pairs_image[4]["prior"])
        base64_img10 = encode_image(example_pairs_image[4]["next"])
        shot5.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img9}"
            }
        })
        shot5.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img10}"
            }
        })
        response5 = example_without_knowledge_response_image[4]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": UI_image_model_system_prompt
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": shot3
                },
                {
                    "role": "assistant",
                    "content": response3
                },
                {
                    "role": "user",
                    "content": shot4
                },
                {
                    "role": "assistant",
                    "content": response4
                },
                {
                    "role": "user",
                    "content": shot5
                },
                {
                    "role": "assistant",
                    "content": response5
                },
                {
                    "role": "user",
                    "content": content
                }

            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def prompot_gpt4o_for_all_related_elements(self, question, images):
        content = [
            {
                "type": "text",
                "text": "Please indicate the index number of all elements that are related to this user needs: "+question
            }
        ]

        img1 = encode_image(images[0])
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img1}"
            }
        })

        shot1 = [
            {
                "type": "text",
                "text": "Please indicate the index number of all elements that are related to this user need: "+example_images_all_elements[0]['question']
            }
        ]
        base64_img1 = encode_image(example_images_all_elements[0]['image'])
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        response1 = example_images_all_elements[0]['response']

        shot2 = [
            {
                "type": "text",
                "text": "Please indicate the index number of all elements that are related to this user need: "+example_images_all_elements[1]['question']
            }
        ]
        base64_img2 = encode_image(example_images_all_elements[1]['image'])
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        response2 = example_images_all_elements[1]['response']

        shot3 = [
            {
                "type": "text",
                "text": "Please indicate the index number of all elements that are related to this user need: "+example_images_all_elements[2]['question']
            }
        ]
        base64_img3 = encode_image(example_images_all_elements[2]['image'])
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img3}"
            }
        })
        response3 = example_images_all_elements[2]['response']

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert of using smartphones. You will receive an UI image and a corresponding user need. You need to identify all UI elements on the current UI that related to the user need, and explain a bit. Please follow the output format in the examples and ensure the output is a valid JSON object in a compact format without any additional explanations, escape characters, newline characters, or backslashes."
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": shot3
                },
                {
                    "role": "assistant",
                    "content": response3
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def desktop_check(self, question, images):
        content = [
            {
                "type": "text",
                "text": "If the given image shows a smartphone desktop, please answer Yes. If it is shows an app UI or some other contents insead of a smartphone desktop UI, please answer No"
            }
        ]

        img1 = encode_image(images[0])
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img1}"
            }
        })

        shot1 = [
            {
                "type": "text",
                "text": "If the given image shows a smartphone desktop, please answer Yes. If it is shows an app UI or some other contents insead of a smartphone desktop UI, please answer No"
            }
        ]
        base64_img1 = encode_image("legality_check_exemplars/flight.jpg")
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        response1 = "No"

        shot2 = [
            {
                "type": "text",
                "text": "If the given image shows a smartphone desktop, please answer Yes. If it is shows an app UI or some other contents insead of a smartphone desktop UI, please answer No"
            }
        ]
        base64_img2 = encode_image("legality_check_exemplars/desktop.jpg")
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        response2 = "Yes"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert of using smartphones. You will receive an UI image and you need to recognize whether it is a desktop UI of a smartphone."
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content


    def out_of_domain_check(self, question, images):
        content = [
            {
                "type": "text",
                "text": "If the smartphone app of the displayed UI image has the function to realize the user intent: " + question+ ", please reply Yes, otherwise, reply No."
            }
        ]

        img1 = encode_image(images[0])
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img1}"
            }
        })

        shot1 = [
            {
                "type": "text",
                "text": "If the smartphone app of the displayed UI image has the function to realize the user intent: I want to buy a flight ticket, please reply Yes, otherwise, reply No."
            }
        ]
        base64_img1 = encode_image("legality_check_exemplars/flight.jpg")
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        response1 = "Yes"

        shot2 = [
            {
                "type": "text",
                "text": "If the smartphone app of the displayed UI image has the function to realize the user intent: I want a coffee, please reply Yes, otherwise, reply No."
            }
        ]
        base64_img2 = encode_image("legality_check_exemplars/hospital.jpg")
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        response2 = "No"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert of using smartphones. You will receive an UI image and a user intent. You need to judge whether the smartphone app of the displayed UI image has the function to realize the user intent."
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content



class TextModel:
    def __init__(self, model, temperature, max_tokens):
        self.client = AzureOpenAI(
            api_key="",
            api_version="",
            azure_endpoint=""
        )
        self.model = model
        self.system_prompt = "You are a powerful assistant who can help the user to find supportive file content to support the users' writing. You should be able to understand the text that the user is writing, predict the user's needs for the supportive file content, and summarize such needs."
        self.temperature = temperature
        self.max_tokens = max_tokens

    def intent_generate(self, prompt):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    #"content": "You are a powerful assistant who can help the user to find supportive file content to support the users' writing. You should be able to understand the text that the user is writing, predict the user's needs for the supportive file content, and summarize such needs. The following is the content the user is writing, please generate very short description for the user's requirements for the file content."
                    "content": "你是一个很强大的助手，能够帮助用户在他们的本地知识库中找到支持性的文件来支撑用户的写作。以下是用户正在写的内容，你需要理解用户当前正在写作的内容，预测用户对于支持性文件内容的需求，并用非常简洁的短语（15字以内）来描述他们对于支持性文件内容的需求。"
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def content_generate(self, content_list, prompt, context):
        content = []
        for item in content_list:
            print(item)
            content.append({"type": "text", "text": item})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    #"content": "You are a powerful assistant who can help the user to find supportive file content to support the users' writing. You should be able to understand the text that the user is writing, predict the user's needs for the supportive file content, and summarize such needs. The following is the content the user is writing, please generate very short description for the user's requirements for the file content."
                    "content": "你是一个很强大的助手，能够基于用户所提供的知识材料以及用户的要求来对你已经写完的内容进行续写。请根据此要求: ‘"+prompt+"’来进行续写"
                },
                {
                    "role": "assistant",
                    "content": context
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content
    
    def intent_predict_without_link(self, actions, content_list, context):
        content = []
        for item in content_list:
            print(item)
            content.append({"type": "text", "text": item})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    #"content": "You are a powerful assistant who can help the user to find supportive file content to support the users' writing. You should be able to understand the text that the user is writing, predict the user's needs for the supportive file content, and summarize such needs. The following is the content the user is writing, please generate very short description for the user's requirements for the file content."
                    "content": "你是一个很强大的助手，能够基于用户当前正在创作的内容、想要应用的知识材料、以及用户阅读和搜索知识材料的行为来预测用户接下来打算如何继续创作新的内容。请你基于用户的prompt来预测和列举至少3个用户继续创作新内容的方式和意图，把它们放在一个列表里。"
                },
                {
                    "role": "user",
                    "content": "用户目前正在创作的内容是：" + context+ "\n 你可以分析当前内容的文风或者格式来判断自己需要以何种方式继续书写。例如以何种人称书写，是否需要列表符号进行列举，书面学术文章的风格还是工作汇报的风格。"
                },
                {
                    "role": "user",
                    "content": "用户需要使用的材料如下：" + str(content) + "\n 你可以分析给定材料之间的关系及其与当前内容间的关系来判断用户可以以何种方式继续书写。例如列举给定材料来支撑当前内容，通过对比给定材料来深入讨论等。"
                },
                {
                    "role": "user",
                    "content": "用户寻找和浏览相关材料的行为如下：" + str(actions) + "\n 你可以分析用户用户的这些行为，来判断用户可能的内容创作意图。例如根据用户关键词搜索的记录来猜想用户需要表达什么内容，根据用户在各个支撑细节上停留的时间以及对比用户的浏览行为，来判断用户可能可以从什么角度来组织材料。"
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def intent_predict_with_link(self, actions, content_list, context):
        content = []

        for link_item in content_list:
            print(link_item)
            #link_item["from"]
            #link_item["label"]
            #link_item["to"]
            content.append({"type": "text", "text": "使用材料的角度是："+ link_item["label"] + "\n" + "材料是：" + link_item["from"] + "\n" + " "+ link_item["to"]})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    #"content": "You are a powerful assistant who can help the user to find supportive file content to support the users' writing. You should be able to understand the text that the user is writing, predict the user's needs for the supportive file content, and summarize such needs. The following is the content the user is writing, please generate very short description for the user's requirements for the file content."
                    "content": "你是一个很强大的助手，能够基于用户当前正在创作的内容、想要应用的知识材料、以及用户阅读和搜索知识材料的行为来预测用户接下来打算如何继续创作新的内容。请你基于用户的prompt来预测和列举至少3个用户继续创作新内容的方式和意图，把它们放在一个列表里。"
                },
                {
                    "role": "user",
                    "content": "用户目前正在创作的内容是：" + context+ "\n 你可以分析当前内容的文风或者格式来判断自己需要以何种方式继续书写。例如以何种人称书写，是否需要列表符号进行列举，书面学术文章的风格还是工作汇报的风格。"
                },
                {
                    "role": "user",
                    "content": "用户需要使用的材料以及他们对于使用这些材料的方式的标注如下：" + str(content) + "\n 你可以分析给定材料之间的关系及其与当前内容间的关系来判断用户可以以何种方式继续书写。例如列举给定材料来支撑当前内容，通过对比给定材料来深入讨论等。请严格遵守用户所希望的使用材料的方式。"
                },
                {
                    "role": "user",
                    "content": "用户寻找和浏览相关材料的行为如下：" + str(actions) + "\n 你可以分析用户用户的这些行为，来判断用户可能的内容创作意图。例如根据用户关键词搜索的记录来猜想用户需要表达什么内容，根据用户在各个支撑细节上停留的时间以及对比用户的浏览行为，来判断用户可能可以从什么角度来组织材料。"
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def linked_content_generate(self, content_list, prompt, context):
        content = []
        for link_item in content_list:
            print(link_item)
            #link_item["from"]
            #link_item["label"]
            #link_item["to"]
            content.append({"type": "text", "text": "<用户对所给出内容的关联性标注>" + link_item["label"] + "\n" + " " + link_item["from"] + "\n" + " "+ link_item["to"]})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    #"content": "You are a powerful assistant who can help the user to find supportive file content to support the users' writing. You should be able to understand the text that the user is writing, predict the user's needs for the supportive file content, and summarize such needs. The following is the content the user is writing, please generate very short description for the user's requirements for the file content."
                    "content": "你是一个很强大的助手，能够基于用户所提供的知识材料以及用户的要求来对你已经写完的内容进行续写。请根据此要求: ‘"+prompt+"’来进行续写"
                },
                {
                    "role": "assistant",
                    "content": context
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content


    def get_embedding(self,text):
        response = self.client.embeddings.create(
            input = text,
            model= "text-embedding-ada-002"
        )
        #print(response)
        #print(response.data[0].embedding)

        return True, np.array(response.data[0].embedding)

    def screen_function_explanation(self,image_path,prompt):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        base64_img = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个对于手机app交互界面非常了解的人，现在一位老人想要实现提示词中所述的目标，但是他看不懂当前手机页面的内容，不知道每一项功能代表什么意思，请你简要概括当前页面的主要功能，注意避免用太过专业的术语。"
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content


    def relevant_element_explanation(self, image_path, screen_brev, prompt):
        content = [
            {
                "type": "text",
                "text": prompt + "\n" + screen_brev
            }
        ]
        base64_img = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant who can identify the key UI elements that may related to users' intention and allow users to select personalized parameters, and explain the functions of those UI elements. Please answer the element_index_number of the key UI elements that are related with users' intention, generate corresponding explanations, and return the dictionary of them with the form of {screen_index_number: explanation, screen_index_number: explanation...}"
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def last_step_identification(self, image_path, prompt):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        base64_img = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

        shot_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        shot1 = [
            {
                "type": "text",
                "text": "我想买张船票"
            }
        ]
        base64_img1 = encode_image(os.path.join(shot_dir_path,"case1.png"))
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        response1 = "False"

        shot2 = [
            {
                "type": "text",
                "text": "我想买张船票"
            }
        ]
        base64_img2 = encode_image(os.path.join(shot_dir_path,"case2.png"))
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        response2 = "True"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant who can identify whether the current screen displays the last step to collect user's information. The last step means users' related information can be collected completely and after this step, the user can directly submit the form data or move to the payment. Please answer True or False."
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def single_screen_function_identification(self, screenshot_path, screen_brev, exemplar, prompt):

        content = [
            {
                "type": "text",
                "text": prompt + "\n" + screen_brev
            }
        ]
        base64_img = encode_image(screenshot_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

        shot_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        base64_img1 = encode_image(os.path.join(shot_dir_path, "14_screenshot.png"))
        shot1 = [
            {
                "type": "text",
                "text": exemplar[0]["instruction"] + "\n" + exemplar[0]["input"][14]
            }
        ]
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        response1 = json.dumps({"element_index_number": 201})


        base64_img2 = encode_image(os.path.join(shot_dir_path, "23_screenshot.png"))
        shot2 = [
            {
                "type": "text",
                "text": exemplar[0]["instruction"] + "\n" + exemplar[0]["input"][23]
            }
        ]
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        response2 = json.dumps({"element_index_number": 46})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant who understand the user's intended function according to the user's prompt. Besides the user's prompt, you are offered a list, each item of which is a UI element represented as a dictionary which contains the attributes of the UI element such as 'text', 'class' and so on. You need to find the UI element that provide the function the user need to move forward to their intended service. Please answer the index number of the UI element within the UI screen with a JSON format: {\"element_index_number\": the number}"
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def seek_function(self, screenList, exemplar, prompt):
        screenList = json.dumps(screenList)
        content = [
            {
                "type": "text",
                "text": prompt + "\n" + screenList
            }
        ]
        shot1 = [
            {
                "type": "text",
                "text": exemplar[0]["instruction"] + "\n" + exemplar[0]["input"]
            }
        ]
        response1 = exemplar[0]["output"]

        shot2 = [
            {
                "type": "text",
                "text": exemplar[1]["instruction"] + "\n" + exemplar[1]["input"]
            }
        ]
        response2 = exemplar[1]["output"]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant who understand the user's intended function according to the user's prompt. Besides the user's prompt, you are offered a list, each item of which is a list of UI elements within the same UI screen. Each UI element is represented as a dictionary which contains the attributes of the UI element such as 'boundLeft', 'boundRight', 'boundTop', 'boundBottom', 'text', 'clickable' and so on. You need to find the UI element that provide the function the user need. Please answer with the index number of the UI screen which contains that UI element, as well as the index number of the UI element within the UI screen."
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def app_seek(self, applist,prompt):
        content = [
            {
                "type": "text",
                "text": "applist: "+ str(applist)+"\n"+"user requirements: "+prompt
            }
        ]

        shot1 = [
            {
                "type": "text",
                "text": "applist: "+ str(["Ctrip", "Luckin coffee"])+"\n"+"user requirements: "+"I want to book a flight ticket"
            }
        ]
        response1 = "Ctrip"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Please select the most possible app provided in the  applist that provide functions satisfy user requirements"
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def translate(self, prompt):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "If the prompot is in English, please translate the user prompt into Chinese. If it is in Chinese, keep it as Chinese."
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content


    def summarize_image(self, prompt, image_path):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        base64_img = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")
        
        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def prompt_image(self, prompt, image_path):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        base64_img = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

    def context_judge(self, image_path, app):
        content = [
            {
                "type": "text",
                "text": "Is the given UI screen belongs to the app "+ app + "? Please answer Yes or No."
            }
        ]
        base64_img = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}"
            }
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a powerful smartphone assistant, who can judge whether the given UI screen belongs to a certain smartphone app. You only need to answer Yes or No."
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        #print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content



    def few_shot_prompot_gpt4o_response(self, prompt):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]

        shot1 = [
            {
                "type": "text",
                "text": example_pairs[0]["instruction"] + "\n" + example_pairs[0]["input"]
            }
        ]
        response1 = example_without_knowledge_response[0]

        shot2 = [
            {
                "type": "text",
                "text": example_pairs[1]["instruction"] + "\n" + example_pairs[1]["input"]
            }
        ]
        response2 = example_without_knowledge_response[1]

        shot3 = [
            {
                "type": "text",
                "text": example_pairs[2]["instruction"] + "\n" + example_pairs[2]["input"]
            }
        ]
        response3 = example_without_knowledge_response[2]

        shot4 = [
            {
                "type": "text",
                "text": example_pairs[3]["instruction"] + "\n" + example_pairs[3]["input"]
            }
        ]
        response4 = example_without_knowledge_response[3]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": response2
                },
                {
                    "role": "user",
                    "content": shot3
                },
                {
                    "role": "assistant",
                    "content": response3
                },
                {
                    "role": "user",
                    "content": shot4
                },
                {
                    "role": "assistant",
                    "content": response4
                },
                {
                    "role": "user",
                    "content": content
                }

            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        print(response.choices[0].message.content)
        print(response)

        if "error" not in response:
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            print_with_color(f"Request cost is "
                             f"${'{0:.4f}'.format(prompt_tokens / 1000000 * 2.5 + completion_tokens / 1000000 * 10)}",
                             "yellow")

        else:
            return False, response.error.message
        return True, response.choices[0].message.content

if __name__ == '__main__':
    configs = load_config()
    text_model = TextModel(model=configs["OPENAI_API_MODEL"], temperature=configs["TEMPERATURE"], max_tokens=configs["MAX_TOKENS"])
    prompt = "为了加速教育现代化进程，实现从教育大国向教育强国的跨越，我国政府坚持不懈地推动教育领域全面深化改革，利用科技手段提升教育质量，优化资源配置，并积极引导以人工智能为代表的新一代信息技术与教育核心场景的深度融合。"
    #_,file_intent = text_model.intent_generate(prompt)
    #print(file_intent)

    context = "教育，作为国家发展的基石，肩负着培育未来社会栋梁的重要使命。随着我国教育强国战略的推进，AI 与教育深度融合，成为推动教育现代化、实现教育强国战略的关键力量。从政策的顶层设计到技术的创新实践，AI 教育正逐渐从理念落地，在提升教育公平与效率、培养面向未来的复合型人才等方面展现出巨大潜力。一、行业发展概况 1、AI赋能教育：构建教育强国的战略路径 “教育兴盛则国家兴盛，教育强大则国家强大”，教育作为国家的根本大计，始终被置于优先发展的战略高度。为了加速教育现代化进程，实现从教育大国向教育强国的跨越，我国政府坚持不懈地推动教育领域全面深化改革，利用科技手段提升教育质量，优化资源配置，并积极引导以人工智能为代表的新一代信息技术与教育核心场景的深度融合。"
    prompt = "介绍我国如何规划新一代信息技术与教育场景的深入融合"
    content1 = "《5G网络建设指导意见 2021》加快5G网络部署，赋能智能教育与产业升级。文件指出要加强5G与AI、物联网等新兴技术的融合应用，提升网络覆盖和服务质量。支持5G在远程医疗、智慧城市等场景的创新实践。"
    content2 = "《中国新一代人工智能发展报告2020》利用AI助进仿真工作场景(如流程工程理、智能制造等)，提供沉浸式实践体验，弥补传统实训资源不足的短板。报告还强调了人工智能在教育、医疗、交通等领域的广泛应用前景，并提出了加强基础研究和人才培养的建议。未来将持续推动AI与实体经济深度融合。"
    contents = [content1, content2]
    _,out=text_model.content_generate(contents, prompt, context)
    print(out)


    #UI_text_model.summarize_image(prompt, "demo.jpg")

    #mllm = OpenAIModel(model=configs["OPENAI_API_MODEL"],
    #                   temperature=configs["TEMPERATURE"],
    #                   max_tokens=configs["MAX_TOKENS"])

    #before = "case2.png"
    #after = "case1.png"
    #status, rsp = mllm.few_shot_prompot_gpt4o_response(user_prompt, [before, after])

    #image = "set_of_mark/boat.jpg"
    #status, rsp = mllm.prompot_gpt4o_for_all_related_elements("我要买船票去鼓浪屿", [image])

    #rsp = json.loads(rsp)

    #mllm.intent_generate()


    #print(rsp['ids'])

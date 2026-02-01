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
from json_repair import repair_json



#UI_image_model_system_prompt = "You are an ordinary smartphone user who can understand the transition logic between consecutive GUI screens. You will be given a pair of consecutive smartphone GUI screens, you need to identify the index number of the UI element that link the given UI screen to the target UI screen describe in texts. If you fail to do this, also explain your reason."

same_ui_principle_system_prompt = "You are a helpful assistant who can can understand the semantic of the given UI screens and judge whether the given UI screens represent the same user interfaces. Please note the following principles to help you make the decision. 1) The same UI screen does not mean that they should be identiccal at each pixel but their primary functions and the state of the primary UI elements should be the same. 2) Even some slight differences appear between two same UI screens, they should be mainly from the differences of dynamic contents or advertisements. 3) If the given UI screens are of the same UI, that means there is no way for them to transition between each other."
worth_ui_principle_system_prompt = "You are a helpful assistant who can can understand the semantic of the given UI screen and judge whether the given UI screen represent provides valuable functions of the app for you to explore. Please note the following principles to help you make the decision. 1) Advertising screens are commonly not worth to explore since they are content driven and do not reflect the apps' structure and interaction patterns. 2) If the screen presents simple UI patterns such as fragments for calendar, softkeyboard, location selection and so on, they should be considered as less valuable to explore. 3) If the UI screen is presenting a smartphone web page and indicating that you have already out of the bound of the initial smartphone app, it should be regarded as not valuable to explore."
uni_elements_system_prompt = "You are a helpful assistant who can can understand the semantic of the given UI screen. You should understand the json representations and screenshots of two UI screens to select common UI elements appear in these two screens."
smart_back_system_prompt = "You are a helpful assistant who can understand the transition logic between consecutive GUI screens. You will be given a pair of consecutive smartphone GUI screens, you need to identify the bounding box of the UI element that link the current UI screen to go back to the prior UI screen."

user_prompt = "Please judge whether the given two UI screens are of the same user interface or not. Please answer with Yes or No"
user_prompt_worth_ui_judgement = "Please judge whether the given UI screen is worth to explore. Please answer with Yes or No"
uni_elements_prompt = "You will be provided with two json lists representing the UI element from two UI screens. One is from the prior screen and the other is from the current screen. Please compare the given json representations of UI elements, select the common elements hold by both screens, and generate a new json list representing the common UI elements (also remove advertisement elements). Please note that even the same UI elements could have some position variations. The position of each UI element is recorded with 4 keys: boundLeft, boundTop, boundRight, boundBottom. If you find that the same UI element have a slight position bias in two screens, you should use boundLeftStatic, boundTopStatic, boundRightStatic, boundBottomStatic to keep the position of the UI element in the prior screen, and use boundLeft, boundTop, boundRight, and boundBottom to record the position of the UI element in the current screen. Elements with illigal position should also be removed such as the boundLeft is larger than boundRight or boundBottom is higher than boundTop"
smart_back_prompt = "Please identify the UI element bounding box which can lead you from the current UI screen to go back to its prior UI screen. Please answer with a dictionary with four keys: boundLeft, boundTop, boundRight, boundBottom"

example_pairs_image = [
    {"prior": "static/exemplars/same/1before.jpg", "current": "static/exemplars/same/1after.jpg", "thought": "1) Both screens present the same key services of the App Ctrip. 2) Although the background content shows some differences, such differences are from the dynamic contents rather than the different key functions. 3) I also don't see the clear transition between these two screens. Therefore, both screens should be the same UI screen." ,"label": "Yes"},
    {"prior": "static/exemplars/same/2before.jpg", "current": "static/exemplars/same/2after.jpg", "thought": "1) Both screens present the page of recommendations for holiday attractions. 2) Although the recommended content shows some differences, such differences are from the dynamic contents rather than the different key functions provided by this page. 3) I also don't see the clear transition between these two screens. Therefore, both screens should be the same UI screen." ,"label": "Yes"},
    {"prior": "static/exemplars/different/1before.jpg", "current": "static/exemplars/different/1after.jpg", "thought": "1) One screen presents the services of buying a boat ticket while the other screen presents the function of buying a bus ticket. 2) The differences of these screens are mainly due to the different services they provide, and the functions for these two services are different. 3) By clicking the title \'boat\' or \'bus\', the two screens can transition between each other. Therefore, the given two screens are different.", "label": "No"},
    {"prior": "static/exemplars/different/2before.jpg", "current": "static/exemplars/different/2after.jpg", "thought": "1) Both screens present the panel of selecting holidays. One screen presents no selection while the other presents an item is selected. 2) The differences between the two screens are based on the different state of key UI elements. 3) By selecting an item presented in the list, one UI screen can transition to the state presented in the other screen. Therefore, the given two screens are different.", "label": "No"}]

example_worthness_image = [
    {"img": "static/exemplars/noworth/1.jpg", "thought": "This page is not an advertising or web page but it only presents interaction patterns for selecting locations, there is no need to explore more on this screen." ,"label": "No"},
    {"img": "static/exemplars/worth/1.jpg", "thought": "This page is not an advertising or web page, it presents a page for selecting drinks and contains various interaction patterns such as side menu, floating shopping bag, and add buttons. I think it is worth to explore." ,"label": "Yes"},
]

example_pairs_uni_elements = [
    {"prior": "static/exemplars/eleUpdate/1before.jpg", "prior_json": "static/exemplars/eleUpdate/1before.json", "current": "static/exemplars/eleUpdate/1current.jpg", "current_json": "static/exemplars/eleUpdate/1current.json", "output": "static/exemplars/eleUpdate/1final.json"},
    {"prior": "static/exemplars/eleUpdate/2before.jpg", "prior_json": "static/exemplars/eleUpdate/2before.json", "current": "static/exemplars/eleUpdate/2current.jpg", "current_json": "static/exemplars/eleUpdate/2current.json", "output": "static/exemplars/eleUpdate/2final.json"}]

example_pairs_back = [
    {"prior": "static/exemplars/back/1before.jpg", "current": "static/exemplars/back/1after.jpg", "current_json": "static/exemplars/back/1after.json", "thought": "On the current screen, the close button of the filter pannel can lead the current screen to go back to the prior screen. It's index number is 1, by finding its corresponding json item of the current UI screen, the bounding box is: " ,"output":{"boundLeft": 46, "boundTop": 767, "boundRight": 190, "boundBottom": 825}},
    ]

'''
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

def load_json(json_path):
    with open(json_path, 'r') as json_file:
        return json.load(json_file)

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

    def single_UI_worthness(self,image):
        content = [
            {
                "type": "text",
                "text": user_prompt_worth_ui_judgement
            }
        ]
        img = encode_image(image)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img}"
            }
        })
        
        shot1 = [
            {
                "type": "text",
                "text": user_prompt_worth_ui_judgement
            }
        ]
        base64_img1 = encode_image(example_worthness_image[0]["img"])
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        thought1 = example_worthness_image[0]["thought"]
        response1 = example_worthness_image[0]["label"]

        shot2 = [
            {
                "type": "text",
                "text": user_prompt_worth_ui_judgement
            }
        ]
        base64_img2 = encode_image(example_worthness_image[1]["img"])
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        thought2 = example_worthness_image[1]["thought"]
        response2 = example_worthness_image[1]["label"]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": worth_ui_principle_system_prompt
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": thought1+ '\n' + response1
                },
                {
                    "role": "user",
                    "content": shot2
                },
                {
                    "role": "assistant",
                    "content": thought2+ '\n' + response2
                },
                {
                    "role": "user",
                    "content": content
                }

            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print("api",response.choices[0].message.content)
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

    def same_screen_recognition_few_shot_prompot(self, images):
        content = [
            {
                "type": "text",
                "text": user_prompt
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
        base64_img2 = encode_image(example_pairs_image[0]['current'])
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
        thought1 = example_pairs_image[0]['thought']
        response1 = example_pairs_image[0]['label']
        '''
        shot2 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img3 = encode_image(example_pairs_image[1]["prior"])
        base64_img4 = encode_image(example_pairs_image[1]["current"])
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
        thought2 = example_pairs_image[1]['thought']
        response2 = example_pairs_image[1]['label']
        '''
        shot3 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img5 = encode_image(example_pairs_image[2]["prior"])
        base64_img6 = encode_image(example_pairs_image[2]["current"])
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
        thought3 = example_pairs_image[2]['thought']
        response3 = example_pairs_image[2]['label']
        '''
        shot4 = [
            {
                "type": "text",
                "text": user_prompt
            }
        ]
        base64_img7 = encode_image(example_pairs_image[3]["prior"])
        base64_img8 = encode_image(example_pairs_image[3]["current"])
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
        thought4 = example_pairs_image[3]['thought']
        response4 = example_pairs_image[3]['label']
        '''
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": same_ui_principle_system_prompt
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": thought1+ '\n' + response1
                },
                {
                    "role": "user",
                    "content": shot3
                },
                {
                    "role": "assistant",
                    "content": thought3+ '\n' + response3
                },
                {
                    "role": "user",
                    "content": content
                }

            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print("api",response.choices[0].message.content)
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

    def smart_back(self, elements, image):
        content = [
            {
                "type": "text",
                "text": smart_back_prompt
            }
        ]

        img = encode_image(image)
        '''
        content.append(
            {
                "type": "text",
                "text": "Current UI screen"
            }
        )
        '''
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img}"
            }
        })
        content.append(
            {
                "type": "text",
                "text": "Json representations of the current screen:" + str(elements)
            }
        )

        '''
        content.append(
            {
                "type": "text",
                "text": "Prior screen that you need to go back to"
            }
        )
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img2}"
            }
        })
        '''
        
        shot1 = [
            {
                "type": "text",
                "text": smart_back_prompt
            }
        ]
        #base64_img1 = encode_image(example_pairs_back[0]['prior'])
        base64_img2 = encode_image(example_pairs_back[0]['current'])
        json_current = load_json(example_pairs_back[0]['current_json'])
        output = example_pairs_back[0]['output']
        #thought = example_pairs_back[0]['thought']
        '''
        shot1.append(
            {
                "type": "text",
                "text": "Current UI screen"
            }
        )
        '''
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        shot1.append(
            {
                "type": "text",
                "text": "Json representations of the current screen:" + str(json_current)
            }
        )
        '''
        shot1.append(
            {
                "type": "text",
                "text": "Prior screen that you need to go back to"
            }
        )
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        '''
        response1 = output

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": smart_back_system_prompt
                },
                {
                    "role": "user",
                    "content": shot1
                },
                {
                    "role": "assistant",
                    "content": str(response1)
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print("api",response.choices[0].message.content)
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

    def uni_elements(self, elements, images):
        content = [
            {
                "type": "text",
                "text": uni_elements_prompt
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
        content.append(
            {
                "type": "text",
                "text": "Json representations of the prior screen:" + str(elements[0])
            }
        )
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img2}"
            }
        })
        content.append(
            {
                "type": "text",
                "text": "Json representations of the current screen:" + str(elements[1])
            }
        )

        shot1 = [
            {
                "type": "text",
                "text": uni_elements_prompt
            }
        ]
        base64_img1 = encode_image(example_pairs_uni_elements[0]['prior'])
        base64_img2 = encode_image(example_pairs_uni_elements[0]['current'])
        json_prior = load_json(example_pairs_uni_elements[0]['prior_json'])
        json_current = load_json(example_pairs_uni_elements[0]['current_json'])
        output = load_json(example_pairs_uni_elements[0]['output'])
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        shot1.append(
            {
                "type": "text",
                "text": "Json representations of the prior screen:" + str(json_prior)
            }
        )
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        shot1.append(
            {
                "type": "text",
                "text": "Json representations of the current screen:" + str(json_current)
            }
        )
        response1 = str(output)

        shot2 = [
            {
                "type": "text",
                "text": uni_elements_prompt
            }
        ]
        base64_img1 = encode_image(example_pairs_uni_elements[1]['prior'])
        base64_img2 = encode_image(example_pairs_uni_elements[1]['current'])
        json_prior = load_json(example_pairs_uni_elements[1]['prior_json'])
        json_current = load_json(example_pairs_uni_elements[1]['current_json'])
        output = load_json(example_pairs_uni_elements[1]['output'])
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        shot2.append(
            {
                "type": "text",
                "text": "Json representations of the prior screen:" + str(json_prior)
            }
        )
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        shot2.append(
            {
                "type": "text",
                "text": "Json representations of the current screen:" + str(json_current)
            }
        )
        response2 = str(output)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": uni_elements_system_prompt
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

        print("api",response.choices[0].message.content)
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

    def prompot_gpt4o_for_all_related_elements(self, question, images, metadata_path):
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

    def app_select(self, app_list, images):
        content = [
            {
                "type": "text",
                "text": str(app_list)
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
                "text": str(["Ctrip", "Luckin coffee", "qdmedical160","Qunar"])
            }
        ]
        base64_img1 = encode_image("legality_check_exemplars/flight.jpg")
        shot1.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img1}"
            }
        })
        response1 = "Ctrip"

        shot2 = [
            {
                "type": "text",
                "text": str(["Ctrip", "Luckin coffee", "qdmedical160","Qunar"])
            }
        ]
        base64_img2 = encode_image("legality_check_exemplars/hospital.jpg")
        shot2.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img2}"
            }
        })
        response2 = "qdmedical160"

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



class UITextModel:
    def __init__(self, model, temperature, max_tokens):
        self.client = AzureOpenAI(
            api_key="",
            api_version="",
            azure_endpoint=""
        )
        self.model = model
        self.system_prompt = "You are a powerful smartphone assistant who can understand the semantic meaning of smartphone UI elements, describe them with suitable captions or alt texts and identify the most possible UI element to complete a certain task."
        self.temperature = temperature
        self.max_tokens = max_tokens

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

    def app_select(self, applist,prompt):
        # 在给定applist里面寻找可能的app并返回可能app的列表
        content = [
            {
                "type": "text",
                "text": "applist: "+ str(applist)+"\n"+"user requirements: "+prompt
            }
        ]

        shot1 = [
            {
                "type": "text",
                "text": "applist: "+ str(["Ctrip", "Luckin coffee", "qdmedical160","Qunar"])+"\n"+"user requirements: "+"I want to book a flight ticket"
            }
        ]
        response1 = "Ctrip,Qunar"

        shot2 = [
            {
                "type": "text",
                "text": "applist: "+ str(["Ctrip", "Luckin coffee", "qdmedical160","Qunar"])+"\n"+"user requirements: "+"我要喝咖啡"
            }
        ]
        response2 = "Luckin coffee"

        shot3 = [
            {
                "type": "text",
                "text": "applist: "+ str(["Ctrip", "Luckin coffee", "qdmedical160","Qunar"])+"\n"+"user requirements: "+"我要充电话费"
            }
        ]
        response3 = str([])

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Please select possible apps provided in the  applist that provide functions satisfy user requirements"
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

    def conversation_back(self, prompt):
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
                    "content": "Please according to the conversation history provided to you, generate feedback to ask the user specify their needs clearly. (Use Chinese)"
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

    def app_conversation_back(self, prompt):
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
                    "content": "Please answer to the user's question strictly within 15 words. No more words please. (Use Chinese)"
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
    #UI_text_model = UITextModel(model=configs["OPENAI_API_MODEL"], temperature=configs["TEMPERATURE"], max_tokens=configs["MAX_TOKENS"])
    #prompt = "Please generate the summarization for the given smartphone UI. Describe the main contents or functions are in this UI screen"
    #UI_text_model.summarize_image(prompt, "demo.jpg")

    mllm = OpenAIModel(model=configs["OPENAI_API_MODEL"],
                       temperature=configs["TEMPERATURE"],
                       max_tokens=configs["MAX_TOKENS"])

    #before = "case2.png"
    #after = "case1.png"
    #status, rsp = mllm.few_shot_prompot_gpt4o_response(user_prompt, [before, after])

    '''
    image = "set_of_mark/boat.jpg"
    status, rsp = mllm.prompot_gpt4o_for_all_related_elements("我要买船票去鼓浪屿", [image])

    rsp = json.loads(rsp)

    print(rsp['ids'])
    '''


    '''
    elements = [[{"boundLeft":116,"boundTop":315,"boundRight":207,"boundBottom":406,"class":"android.widget.ImageView","checkable":False,"checked":False,"clickable":False,"enabled":True,"focusable":False,"focused":False,"long-clickable":False,"password":False,"scrollable":False,"selected":False},{"boundLeft":102,"boundTop":445,"boundRight":219,"boundBottom":494,"class":"android.widget.TextView","text":"Hotels","checkable":False,"checked":False,"clickable":False,"enabled":True,"focusable":False,"focused":False,"long-clickable":False,"password":False,"scrollable":False,"selected":False}],[{"boundLeft":34,"boundTop":258,"boundRight":612,"boundBottom":355,"class":"android.widget.TextView","text":"Hotels & Homes","checkable":False,"checked":False,"clickable":False,"enabled":True,"focusable":False,"focused":False,"long-clickable":False,"password":False,"scrollable":False,"selected":False},{"boundLeft":68,"boundTop":444,"boundRight":124,"boundBottom":506,"class":"android.widget.TextView","text":"","checkable":False,"checked":False,"clickable":False,"enabled":True,"focusable":False,"focused":False,"long-clickable":False,"password":False,"scrollable":False,"selected":False}]]
    images = ["/Users/xiaozhuhu/Desktop/AppFlating_online_UTG_annotate_tool/static/appData/ctrip.english/0_screenshot.jpg", "/Users/xiaozhuhu/Desktop/AppFlating_online_UTG_annotate_tool/static/appData/ctrip.english/1_screenshot.jpg" ]
    _, new_node = mllm.uni_elements(elements,images)
    out = repair_json(new_node)
    out = json.loads(out)
    print("new_node",out)
    '''

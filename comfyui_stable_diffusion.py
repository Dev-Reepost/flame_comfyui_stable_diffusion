##########################################################################
#
# Filename: comfyui.py
#
# Copyright (c) 2024 Julien Martin
# All rights reserved.
#
###########################################################################

from __future__ import print_function

import random
import sys
import os
import os.path
import json
import uuid
import glob
import shutil
import tempfile
import webbrowser
from enum import Enum
from pathlib import Path
from pprint import pprint

import pybox_v1 as pybox

from comfyui_api_ws import queue_prompt
from comfyui_api_ws import prompt_execution
from comfyui_api_ws import interrupt_execution
from comfyui_api_ws import COMFYUI_HOSTNAME
from comfyui_api_ws import COMFYUI_HOSTPORT


# ComfyUI Stable diffusion constants 
COMFYUI_WORKFLOW_NAME = "ComfyUI SD"

COMFYUI_WORKING_DIR = "/Volumes/silo2/002_COMFYUI"
COMFYUI_WORKFLOWS_DIR = str(Path(COMFYUI_WORKING_DIR) / "workflows")
COMFYUI_WORKFLOW_DIR = str(Path(COMFYUI_WORKFLOWS_DIR) / "stable-diffusion" / "api")
COMFYUI_WORKFLOW_FILENAME = "comfyui_sd_workflow_api.json"
COMFYUI_WORKFLOW_PATH = str(Path(COMFYUI_WORKFLOW_DIR) / COMFYUI_WORKFLOW_FILENAME)

COMFYUI_INPUT_DIR = str(Path(COMFYUI_WORKING_DIR) / "in")
COMFYUI_OUTPUT_DIR = str(Path(COMFYUI_WORKING_DIR) / "out")
COMFYUI_OUTPUT_DEFAULT_IMAGE_PREFIX = "ComfyUI"
COMFYUI_OUTPUT_DEFAULT_INITIAL_VERSION = 1

COMFYUI_MODELS_DIR_PATHS = [
    str(Path(COMFYUI_WORKING_DIR) / "models" / "checkpoints"),
    str(Path(COMFYUI_WORKING_DIR) / "models" / "diffusers")
    ]
COMFYUI_MODELS_EXCLUDED_DIRS = [
    ".git", 
    "doc", 
    "tokenizer", 
    "text_encoder", 
    "unet", 
    "scheduler"
    ]
COMFYUI_MODELS_FILETYPES = [
    "safetensors", 
    "ckpt"
    ]

DEFAULT_SAMPLING_STEPS = 20

DEFAULT_NUM_PROMPTS = 5

DEFAULT_IMAGE_FORMAT = "exr"
DEFAULT_IMAGE_WIDTH = 1920
DEFAULT_IMAGE_HEIGHT = 1080 
IMAGE_WIDTH_MAX = 7680 
IMAGE_HEIGHT_MAX = 4320 
def EMPTY_IMAGE_FILEPATH(color, w=DEFAULT_IMAGE_WIDTH, h=DEFAULT_IMAGE_HEIGHT):
    filename = color + "_" + str(w) + "-" + str(h) + "." + DEFAULT_IMAGE_FORMAT
    return str(Path(COMFYUI_WORKING_DIR) / "presets" / filename)

UI_HOSTNAME = "Hostname"
UI_HOSTPORT = "Hostport"
UI_WORKFLOW_PATH = "Workflow path"
UI_MODELS_LIST = "Model"
UI_SUBMIT = "Generate image"
UI_OUT_WIDTH = "Width"
UI_OUT_HEIGHT = "Height"
UI_STEPS = "Steps"
UI_PROMPT_PREFIX = "Prompt"
def UI_PROMPT(orientation, p):
    return " ".join([UI_PROMPT_PREFIX, orientation, str(p)]) 

class Status(str, Enum):
    IDLE = "Idle"
    WAITING = "Waiting"
    EXECUTING = "Executing"
    PROCESSED = "Processed"
    FAILED = "Failed"

class PromptSign(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"

class NodeIn(str, Enum):
    FRONT = "Front"
    BACK = "Back"
    MATTE = "Matte"

class NodeOut(str, Enum):
    RESULT = "Result"
    OUTMATTE = "OutMatte"

RED = [1.0, 0.0, 0.0]
GREEN = [0.0, 1.0, 0.0]
BLUE = [0.0, 0.0, 1.0]
YELLOW = [1.0, 1.0, 0.0]
GRAY = [0.14, 0.14, 0.14]

    
class ComfyuiSD(pybox.BaseClass):
    
    hostname = ""
    hostport = ""
    server_address = ""
    server_url = ""
    
    workflow = {}
    workflow_id_to_class_type = {}
    workflow_k_sampler_idx = -1
    workflow_pos_prompt_idx = -1
    workflow_neg_prompt_idx = -1
    workflow_latent_img_idx = -1
    workflow_save_exr_idx = -1
    workflow_model_idx = -1
    
    models = []
    model = ""
    
    prompt_id = ""
    client_id = ""
    
    num_prompts = DEFAULT_NUM_PROMPTS
    workflow_sampling_steps = DEFAULT_SAMPLING_STEPS
    
    ui_processing = Status.IDLE
    is_processing = False
    result = ""
    
    out_frame_pad = 4
    out_img_width = DEFAULT_IMAGE_WIDTH
    out_img_height = DEFAULT_IMAGE_HEIGHT
    image_format = DEFAULT_IMAGE_FORMAT
    out_default_filepath = EMPTY_IMAGE_FILEPATH("black")
    out_filename_prefix = COMFYUI_OUTPUT_DEFAULT_IMAGE_PREFIX
    out_version = COMFYUI_OUTPUT_DEFAULT_INITIAL_VERSION
    out_basename = ""
    out_filepath = ""
    
    
    ##########################################################################
    # Functions inherited from Pybox.BaseClass
    
    def initialize(self):
        print("________")
        print("initialize")
        print("________")
        
        self.set_project_metadata()
        self.init_host_info()
        self.find_models()
        self.load_workflow()
        
        self.set_server_address()
        self.set_file_io()
        self.init_ui()
        
        self.set_state_id("setup_ui")
        self.setup_ui()


    def setup_ui(self):
        print("________")
        print("setup_ui")
        print("________")

        for elem in self.get_ui_changes():
            
            if elem["name"] == UI_SUBMIT:
                submit_on = self.get_global_element_value(UI_SUBMIT)
                if submit_on:
                    self.process_workflow()
                else:
                    self.stop_workflow()
                
            elif elem["name"] == UI_HOSTNAME:
                self.update_host_from_ui()
                
            elif elem["name"] == UI_HOSTPORT:
                self.update_host_from_ui()
        
        
        self.update_ui()
        self.update_output()
    
    def execute(self):
        print("________")
        print("execute")
        print("________")
        
        self.set_state_id("setup_ui")
        self.setup_ui()


    def teardown(self):
        print("________")
        print("teardown")
        print("________")
        
    ##########################################################################
    # Functions not inherited from Pybox.BaseClass

    # UI-related methods
    def init_ui(self):
        
        # ComfyUI pages
        pages = []
        page = pybox.create_page(
            COMFYUI_WORKFLOW_NAME, "Server / Workflow", "Model / Image", "Positive prompt", "Negative prompt", "Action"
            )
        pages.append(page)
        self.set_ui_pages_array(pages)
        
        col = 0
        # ComfyUI server URL
        host_ip_tf = pybox.create_text_field(
            UI_HOSTNAME, row=0, col=col, value=COMFYUI_HOSTNAME
            )
        self.add_global_elements(host_ip_tf)
        host_port_tf = pybox.create_text_field(
            UI_HOSTPORT, row=1, col=col, value=COMFYUI_HOSTPORT
            )
        self.add_global_elements(host_port_tf)
        # ComfyUI worfklow JSON path
        wfapi_path = pybox.create_file_browser(
            UI_WORKFLOW_PATH, COMFYUI_WORKFLOW_PATH, "json", home=COMFYUI_WORKFLOW_DIR, 
            row=2, col=col, tooltip="Workflow path"
            )
        self.add_global_elements(wfapi_path)
        
        col = 1
        # ComfyUI Stable diffusion models filename
        models_list = pybox.create_popup(
            UI_MODELS_LIST, self.models, value=self.models.index(self.model), default=0, 
            row=0, col=col, tooltip="Stable diffusion model to use"
            )
        self.add_global_elements(models_list)
        
        # ComfyUI 
        out_width = pybox.create_float_numeric(
            UI_STEPS, value=self.workflow_sampling_steps, default=DEFAULT_SAMPLING_STEPS, 
            min=0, max=100, inc=1,
            row=1, col=col, tooltip="Sampling steps number",
            )
        self.add_global_elements(out_width)
        
        # ComfyUI Stable diffusion output image width
        out_width = pybox.create_float_numeric(
            UI_OUT_WIDTH, value=self.out_img_width, default=DEFAULT_IMAGE_WIDTH, 
            min=0, max=IMAGE_WIDTH_MAX, inc=1,
            row=2, col=col, tooltip="Stable diffusion image width",
            )
        self.add_global_elements(out_width)
        # ComfyUI Stable diffusion output image height
        out_height = pybox.create_float_numeric(
            UI_OUT_HEIGHT, value=self.out_img_height, default=DEFAULT_IMAGE_HEIGHT, 
            min=0, max=IMAGE_HEIGHT_MAX, inc=1,
            row=3, col=col, tooltip="Stable diffusion image height",
            )
        self.add_global_elements(out_height)
        
        col = 2
        # ComfyUI Stable diffusion positive prompts conditioning
        for p in range(self.num_prompts):
            prompt = pybox.create_text_field(
                    UI_PROMPT(PromptSign.POSITIVE, p), row=p, col=col, value=""
                )
            self.add_global_elements(prompt)
        
        col = 3
        # ComfyUI Stable diffusion negative prompts conditioning
        for p in range(self.num_prompts):
            prompt = pybox.create_text_field(
                    UI_PROMPT(PromptSign.NEGATIVE, p), row=p, col=col, value=""
                )
            self.add_global_elements(prompt)
        
        col = 4
        # ComfyUI workflow actions
        wfapi_submit = pybox.create_toggle_button(
            UI_SUBMIT, False, default=False, 
            row=0, col=col, tooltip="Queue workflow on ComfyUI server"
            )
        self.add_global_elements(wfapi_submit)

        wfapi_proc = pybox.create_color(
            self.ui_processing, default=GRAY, values=GRAY, 
            row=1, col=col, tooltip="Workflow execution state on server"
            )
        self.add_global_elements(wfapi_proc)
    
    
    def init_host_info(self):
        self.hostname = COMFYUI_HOSTNAME
        self.hostport = COMFYUI_HOSTPORT
    
    
    def set_server_address(self):
        self.server_address = self.hostname + ":" + self.hostport
        self.server_url = "http://" + self.server_address
    
    
    def find_models(self, dirs=COMFYUI_MODELS_DIR_PATHS):
        models = []
        for model_path in dirs:
            print("Searching for models in {}".format(model_path))
            for _, dirnames, filenames in os.walk(model_path):
                for excl_dir in COMFYUI_MODELS_EXCLUDED_DIRS:
                    if excl_dir in dirnames:
                        dirnames.remove(excl_dir)
                for filename in [f for f in filenames if f.endswith(tuple(COMFYUI_MODELS_FILETYPES))]:
                    print("Found {} model".format(filename))
                    models.append(filename)
        self.models = list(set(models))
    
    
    def set_out_basename(self):
        self.out_basename = "_".join([self.project, self.node_name])
    
    
    def set_out_version(self, dir=COMFYUI_OUTPUT_DIR):
        output_pattern_file = self.out_basename + "*." + self.get_img_format()
        output_pattern_path = str(Path(dir) / output_pattern_file)
        output_files = glob.glob(output_pattern_path)
        output_files.sort()
        if output_files:
            self.out_version = int(output_files[-1].split('_')[-2])
        print(f"Initial output version number: {self.out_version}")
    
    
    def set_out_filepath(self):
        padding = (self.out_frame_pad - len(str(self.out_version)) + 1) * "0"
        version_padded = padding + str(self.out_version)
        basename = "_".join([
            self.project, 
            self.node_name, 
            version_padded, 
            ""
            ]) 
        filename = basename + "." + self.get_img_format()
        self.out_filepath = str(Path(COMFYUI_OUTPUT_DIR) / filename)
    
    
    def set_file_io(self):
        self.set_out_basename()
        self.set_out_version()
        self.set_out_filepath() 
        
        self.set_img_format(self.image_format)
        self.set_in_socket(0, "undefined", "")
        self.remove_in_socket(2)
        self.remove_in_socket(1)
        result_basename = "_".join([self.out_basename, NodeOut.RESULT])
        result_filename = result_basename + "." + self.get_img_format()
        result_path = tempfile.gettempdir() + "/" + result_filename
        self.set_out_socket(0, NodeOut.RESULT, result_path)
    
    
    def load_workflow(self):
        with open(COMFYUI_WORKFLOW_PATH) as f:
            self.workflow = json.load(f)
            self.workflow_id_to_class_type = {id: details['class_type'] for id, details in self.workflow.items()}
            self.workflow_k_sampler_idx = [
                key for key, value in self.workflow_id_to_class_type.items() if value == 'KSampler'
                ][0]
            ksampler_inputs = self.workflow.get(self.workflow_k_sampler_idx)["inputs"]
            self.workflow_model_idx = ksampler_inputs["model"][0]
            self.model = self.workflow.get(self.workflow_model_idx)["inputs"]["ckpt_name"]
            self.workflow_pos_prompt_idx = ksampler_inputs["positive"][0]
            self.workflow_neg_prompt_idx = ksampler_inputs["negative"][0]
            self.workflow_latent_img_idx = ksampler_inputs["latent_image"][0]
            self.workflow_sampling_steps = ksampler_inputs["steps"]
            latent_img_inputs = self.workflow.get(self.workflow_latent_img_idx)["inputs"]
            self.out_img_width = int(latent_img_inputs["width"])
            self.out_img_height = int(latent_img_inputs["height"])
            self.workflow_save_exr_idx = [
                key for key, value in self.workflow_id_to_class_type.items() if value == 'SaveEXR'
                ][0]
            self.out_frame_pad = self.workflow.get(self.workflow_save_exr_idx)["inputs"]["frame_pad"]
    
    
    def set_workflow_model(self):
        
        model_idx = self.get_global_element_value(UI_MODELS_LIST)
        print(model_idx)
        self.model = self.models[model_idx]
        print(self.model)
        self.workflow.get(self.workflow_model_idx)["inputs"]["ckpt_name"] = self.model
    
    
    def set_workflow_prompts(self):
        if self.workflow:
            prompts = {
                    "positive": [],
                    "negative": []
                }
            for p in range(self.num_prompts):
                prompt_name_pos = UI_PROMPT(PromptSign.POSITIVE, p)
                txt = self.get_global_element_value(prompt_name_pos).strip()
                if txt:
                    prompts["positive"].append(txt)
                prompt_name_neg = UI_PROMPT(PromptSign.NEGATIVE, p)
                txt = self.get_global_element_value(prompt_name_neg).strip()
                if txt:
                    prompts["negative"].append(txt)
            self.workflow.get(self.workflow_pos_prompt_idx)["inputs"]["text"] = ", ".join(prompts["positive"])
            self.workflow.get(self.workflow_neg_prompt_idx)["inputs"]["text"] = ", ".join(prompts["negative"])
    
    
    def set_workflow_img_size(self):
        if self.workflow:  
            self.out_img_width = int(self.get_global_element_value(UI_OUT_WIDTH))
            self.workflow.get(self.workflow_latent_img_idx)["inputs"]["width"] = self.out_img_width
            self.out_img_height = int(self.get_global_element_value(UI_OUT_HEIGHT))
            self.workflow.get(self.workflow_latent_img_idx)["inputs"]["height"] = self.out_img_height
    
    
    def set_workflow_filename_prefix(self):
        self.workflow.get(self.workflow_save_exr_idx)["inputs"]["filename_prefix"] = self.out_basename
    
    
    def set_workflow_sampling_steps(self):
        self.workflow_sampling_steps = int(self.get_global_element_value(UI_STEPS))
        self.workflow.get(self.workflow_k_sampler_idx)["inputs"]["steps"] = self.workflow_sampling_steps
        
        
    def process_workflow(self):
        if self.workflow and not self.is_processing:
            self.set_workflow_model()
            self.set_workflow_prompts()
            self.set_workflow_img_size()
            self.set_workflow_ksampler_seed()
            self.set_workflow_filename_prefix()
            self.set_workflow_sampling_steps()
            
            #webbrowser.open(self.server_url, new=0, autoraise=True)
            self.client_id = str(uuid.uuid4())
            self.is_processing = True
            pprint(self.workflow)
            print("Submitting workflow on {} with client id {}".format(self.server_address, self.client_id))
            self.prompt_id = queue_prompt(self.workflow, self.client_id, server_address=self.server_address)
    
    
    def stop_workflow(self):
        if self.client_id and self.is_processing:
            if self.prompt_id:
                resp = interrupt_execution(self.prompt_id, self.client_id, self.server_address)
                print(f"Execution interrupted on server {self.server_address}")
                print(resp)
            self.is_processing = False
            self.set_ui_processing_color(GRAY, Status.IDLE)
    
    
    def generate_ksampler_seed(self):
        seed = random.randint(10**14, 10**16-1) 
        return str(seed)
    
    
    def set_workflow_ksampler_seed(self):
        if self.workflow:
            seed = self.generate_ksampler_seed()
            self.workflow.get(self.workflow_k_sampler_idx)['inputs']['seed'] = seed
    
    
    def set_project_metadata(self):
        self.project = self.get_project()
        self.node_name = self.get_node_name()
        self.resolution = self.get_resolution()

    
    def update_output(self):
        if Path(self.out_filepath).is_file():
            print(f"Copying {self.out_filepath}")
            shutil.copy(self.out_filepath, self.get_out_socket_path(0))
        else:
            print("Copying default empty image")
            shutil.copy(self.out_default_filepath, self.get_out_socket_path(0))
    
    
    def set_ui_processing_color(self, color, ui_label):
        self.remove_global_element(self.ui_processing)
        self.ui_processing = ui_label
        wfapi_proc = pybox.create_color(ui_label, values=color, row=1, col=4)
        self.add_global_elements(wfapi_proc)
    
    
    def update_host_from_ui(self):
        self.hostname = self.get_global_element_value(UI_HOSTNAME)
        self.hostport = self.get_global_element_value(UI_HOSTPORT)
        self.set_server_address()
    
    
    def update_ui(self):
        prompt_executing = False
        if self.is_processing:
            if (self.server_address and 
                self.prompt_id and 
                self.client_id):
                print("Getting workflow execution on {} with client id {}"
                    .format(self.server_address, self.client_id))
                response = prompt_execution(self.server_address, self.client_id, self.prompt_id["prompt_id"])
                if response:
                    prompt_executing = response["executing"]
                    if prompt_executing:
                        self.set_ui_processing_color(BLUE, Status.EXECUTING)
                    else:
                        self.is_processing = False
                        self.set_out_version()
                        self.set_out_filepath()
                        self.set_global_element_value(UI_SUBMIT, False)
                        self.set_ui_processing_color(GREEN, Status.PROCESSED)
                else:
                    self.is_processing = False
                    self.set_global_element_value(UI_SUBMIT, False)
                    self.set_ui_processing_color(RED, Status.FAILED)
            else:
                self.is_processing = False
                self.set_global_element_value(UI_SUBMIT, False)
                self.set_ui_processing_color(RED, Status.FAILED)
        print(self.server_address)
        print(self.prompt_id)
        print(self.client_id)
        print("Processing requested: {}".format(self.is_processing))
        print("Executing: {}".format(prompt_executing))
    
    
def _main(argv):
    print("____________________")
    print("Loading ComfyUI JSON Pybox")
    print("____________________")
    
    # Load the json file, make sure you have read access to it
    p = ComfyuiSD(argv[0])
    # Call the appropriate function
    p.dispatch()
    # Save file
    p.write_to_disk(argv[0])
    
    print("____________________")
    print("Writing ComfyUI JSON Pybox")
    print("____________________")

if __name__ == "__main__":
    _main(sys.argv[1:])
    
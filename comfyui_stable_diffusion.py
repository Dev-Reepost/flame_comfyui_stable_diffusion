##########################################################################
#
# Filename: comfyui_stable_diffusion.py
# Author: Julien Martin
# Created: 2024
#
###########################################################################

from __future__ import print_function

import random
import sys
import json
from enum import Enum
from pathlib import Path
from pprint import pprint

import pybox_v1 as pybox
import pybox_comfyui

from comfyui_client import COMFYUI_WORKING_DIR
from comfyui_client import find_models

from pybox_comfyui import DEFAULT_IMAGE_WIDTH
from pybox_comfyui import DEFAULT_IMAGE_HEIGHT
from pybox_comfyui import IMAGE_HEIGHT_MAX
from pybox_comfyui import IMAGE_WIDTH_MAX
from pybox_comfyui import UI_SUBMIT
from pybox_comfyui import UI_INTERRUPT
from pybox_comfyui import UI_PROMPT
from pybox_comfyui import Color
from pybox_comfyui import LayerOut
from pybox_comfyui import PromptSign


COMFYUI_WORKFLOW_NAME = "ComfyUI SD"
COMFYUI_OPERATOR_NAME = "stable_diffusion"

COMFYUI_MODELS_DIR_PATHS = [
    str(Path(COMFYUI_WORKING_DIR) / "models" / "checkpoints"),
    str(Path(COMFYUI_WORKING_DIR) / "models" / "diffusers")
    ]

UI_MODELS_LIST = "Model"
UI_OUT_WIDTH = "Width"
UI_OUT_HEIGHT = "Height"
UI_STEPS = "Steps"

DEFAULT_SAMPLING_STEPS = 20
DEFAULT_NUM_PROMPTS = 5

    
class ComfyuiSD(pybox_comfyui.ComfyUIBaseClass):
    operator_name = COMFYUI_OPERATOR_NAME
    operator_layers = [LayerOut.RESULT]
    operator_static = True
    
    version = 1
    
    models = []
    model = ""
    
    num_prompts = DEFAULT_NUM_PROMPTS
    sampling_steps = DEFAULT_SAMPLING_STEPS    
    out_img_width = DEFAULT_IMAGE_WIDTH
    out_img_height = DEFAULT_IMAGE_HEIGHT
    
    workflow_model_idx = -1
    workflow_k_sampler_idx = -1
    workflow_pos_prompt_idx = -1
    workflow_neg_prompt_idx = -1
    workflow_latent_img_idx = -1
    workflow_save_exr_result_idx = -1
    
    
    ##########################################################################
    # Functions inherited from Pybox.BaseClass
    
    
    def initialize(self):
        super().initialize()
        
        self.set_state_id("setup_ui")
        self.setup_ui()

    
    def setup_ui(self):
        super().setup_ui()
        
        self.set_state_id("execute")
    
    
    def execute(self):
        super().execute()
        
        if self.out_frame_requested():
            self.submit_workflow()
        
        if self.get_global_element_value(UI_INTERRUPT):
            self.interrupt_workflow()
        
        self.update_workflow_execution()
        self.update_outputs(layers=self.operator_layers)
    

    def teardown(self):
        super().teardown()
    
    
    ##########################################################################
    # Functions not inherited from Pybox.BaseClass

    
    # UI-related methods
    def init_ui(self):
        
        # ComfyUI pages
        pages = []
        page = pybox.create_page(
            COMFYUI_WORKFLOW_NAME, 
            "Server / Workflow", "Model / Image", "Positive prompt", "Negative prompt", "Action"
            )
        pages.append(page)
        self.set_ui_pages_array(pages)
        
        col = 0
        # ComfyUI server URL
        self.set_ui_host_info(col)
        self.set_ui_workflow_path(col, self.workflow_dir, self.workflow_path)
        
        col = 1
        # ComfyUI Stable diffusion models filename
        models_list = pybox.create_popup(
            UI_MODELS_LIST, self.models, value=self.models.index(self.model), default=0, 
            row=0, col=col, tooltip="Stable diffusion model to use"
            )
        self.add_global_elements(models_list)
        
        # ComfyUI 
        out_width = pybox.create_float_numeric(
            UI_STEPS, value=self.sampling_steps, default=DEFAULT_SAMPLING_STEPS, 
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
        self.ui_version_row = 0
        self.ui_version_col = col
        self.set_ui_versions()
        
        self.set_ui_increment_version(row=1, col=col)
        
        self.set_ui_interrupt(row=2, col=col)
        
        self.ui_processing_color_row = 3
        self.ui_processing_color_col = col
        self.set_ui_processing_color(Color.GRAY, self.ui_processing)
    
    
    ###################################
    # Helpers 
    
    
    def set_models(self):
        self.models = find_models(COMFYUI_MODELS_DIR_PATHS)
    
    
    ###################################
    # Workflow
    
    
    def load_workflow(self):
        with open(self.workflow_path) as f:
            print("Loading Workflow")
            self.workflow = json.load(f)
            self.workflow_id_to_class_type = {id: details['class_type'] for id, details in self.workflow.items()}
            self.workflow_k_sampler_idx = [key for key, value in self.workflow_id_to_class_type.items() if value == 'KSampler'][0]
            ksampler_inputs = self.workflow.get(self.workflow_k_sampler_idx)["inputs"]
            self.workflow_model_idx = ksampler_inputs["model"][0]
            self.model = self.workflow.get(self.workflow_model_idx)["inputs"]["ckpt_name"]
            self.workflow_pos_prompt_idx = ksampler_inputs["positive"][0]
            self.workflow_neg_prompt_idx = ksampler_inputs["negative"][0]
            self.workflow_latent_img_idx = ksampler_inputs["latent_image"][0]
            self.sampling_steps = ksampler_inputs["steps"]
            latent_img_inputs = self.workflow.get(self.workflow_latent_img_idx)["inputs"]
            self.out_img_width = int(latent_img_inputs["width"])
            self.out_img_height = int(latent_img_inputs["height"])
            
            save_exr_nodes = [(key, self.workflow.get(key)["inputs"]) 
                            for key, value in self.workflow_id_to_class_type.items() if value == 'SaveEXR']
            self.workflow_save_exr_result_idx = [key for (key, attr) in save_exr_nodes if attr["filename_prefix"] == "Result"][0]
            
            self.out_frame_pad = self.workflow.get(self.workflow_save_exr_result_idx)["inputs"]["frame_pad"]
    
    
    def set_workflow_model(self):
        model_idx = self.get_global_element_value(UI_MODELS_LIST)
        self.model = self.models[model_idx]
        print(f'Workflow SD model: {self.model}')
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
    
    
    def set_workflow_sampling_steps(self):
        self.sampling_steps = int(self.get_global_element_value(UI_STEPS))
        self.workflow.get(self.workflow_k_sampler_idx)["inputs"]["steps"] = self.sampling_steps
    
    
    def set_workflow_ksampler_seed(self):
        if self.workflow:
            seed = str(random.randint(10**14, 10**16-1))
            self.workflow.get(self.workflow_k_sampler_idx)['inputs']['seed'] = seed
    
    
    def workflow_setup(self):
        self.set_workflow_model()
        self.set_workflow_prompts()
        self.set_workflow_img_size()
        self.set_workflow_ksampler_seed()
        self.set_workflow_sampling_steps()
        self.set_workflow_save_exr_filename_prefix([LayerOut.RESULT])
    
    
def _main(argv):
    print("____________________")
    print("Loading JSON Pybox")
    print("____________________")
    
    # Load the json file, make sure you have read access to it
    p = ComfyuiSD(argv[0])
    # Call the appropriate function
    p.dispatch()
    # Save file
    p.write_to_disk(argv[0])
    
    print("____________________")
    print("Writing JSON Pybox")
    print("____________________")


if __name__ == "__main__":
    _main(sys.argv[1:])
    
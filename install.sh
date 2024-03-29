#!/bin/bash
# Install ComfyUI websockets-based client API for Autodesk Flame / Flare

AUTODESK_PATH='/opt/Autodesk'
PYBOX_DIR="$AUTODESK_PATH/shared/presets/pybox"

echo "______________________________________________________"
echo "Installing ComfyUI Stable diffusion for Autodesk Flame"
echo "______________________________________________________"

comfyui_client_filename="comfyui_client.py"
comfyui_client_path="$PYBOX_DIR/$comfyui_client_filename"
if [ ! -f "$comfyui_client_path" ]; then
    echo "Warning: $comfyui_client_path is missing"
    echo "         Install ComfyUI client for Autodesk Flame Pybox first."
fi

comfyui_stable_diffusion_filename="comfyui_stable_diffusion.py"
pybox_handlers_dir=`find "$AUTODESK_PATH/presets" -type d -name 'presets' | grep pybox | grep -v shared | sort | tail -1`
echo "Copying $comfyui_stable_diffusion_filename to $pybox_handlers_dir"
cp $comfyui_stable_diffusion_filename "$pybox_handlers_dir"

echo "Installation terminated"
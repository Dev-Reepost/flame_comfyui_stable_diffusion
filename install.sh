#!/bin/bash
# Install ComfyUI websockets-based client API for Autodesk Flame / Flare

AUTODESK_PATH='/opt/Autodesk/'
PYBOX_DIR="$AUTODESK_PATH/shared/presets/pybox"

echo "______________________________________________________________"
echo "Installing ComfyUI Stable diffusion handler for Autodesk Flame"
echo "______________________________________________________________"

comfyui_api_client="$PYBOX_DIR/comfyui_api_ws.py"
echo "Checking if $comfyui_api_client is installed"
if [ ! -f "$comfyui_api_client" ]; then
    echo "$comfyui_api_client is missing"
    echo "Install ComfyUI client for Pybox first."
    exit 1
fi

pybox_handlers_dir=`find "$AUTODESK_PATH/presets" -type d -name 'presets' | grep pybox | grep -v shared`
echo "Copying ComfyUI Stable diffusion Pybox handler to $pybox_handlers_dir"
cp "comfyui_stable_diffusion.py" "$pybox_handlers_dir"

echo "Installation terminated"
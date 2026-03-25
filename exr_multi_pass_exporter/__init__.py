"""
ComfyUI Custom Node: Multi-Pass EXR Exporter (Chaining Version)
Exports multiple render passes to embedded multi-channel EXR sequences
Uses "Add Pass" nodes that chain together for flexible pass assembly
"""

import sys
import subprocess

# Auto-install dependencies if missing
def install_dependencies():
    """Check and install required dependencies"""
    dependencies = {
        'OpenEXR': 'OpenEXR',
        'Imath': 'Imath'
    }
    
    missing = []
    for module, package in dependencies.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"\n{'='*60}")
        print(f"Multi-Pass EXR Exporter: Installing missing dependencies...")
        print(f"{'='*60}\n")
        
        for package in missing:
            print(f"Installing {package}...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", package
                ])
                print(f"✓ {package} installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"✗ Failed to install {package}: {e}")
                print(f"\nPlease manually install by running:")
                print(f"  pip install {package}")
        
        print(f"\n{'='*60}")
        print(f"Installation complete! Please restart ComfyUI.")
        print(f"{'='*60}\n")

# Run dependency check on load
install_dependencies()

import torch
import numpy as np
import OpenEXR
import Imath
import os
from pathlib import Path


class AddPass:
    """
    Add a single pass to the pass chain.
    Can be chained with other AddPass nodes.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "pass_name": ("STRING", {"default": "pass"}),
            },
            "optional": {
                "passes": ("PASS_CHAIN",),
            }
        }
    
    RETURN_TYPES = ("PASS_CHAIN",)
    RETURN_NAMES = ("passes",)
    FUNCTION = "add_pass"
    CATEGORY = "image/export"

    def add_pass(self, image, pass_name, passes=None):
        """
        Add this pass to the chain.
        """
        # Start a new chain or append to existing
        if passes is None:
            pass_chain = {}
        else:
            pass_chain = passes.copy()
        
        # Add this pass to the chain
        clean_name = pass_name.strip() if pass_name.strip() else "unnamed_pass"
        pass_chain[clean_name] = image
        
        return (pass_chain,)


class MultiPassEXRExporter:
    """
    Exports multiple render passes (beauty, depth, mattes, etc.) into 
    multi-channel EXR image sequences with preserved channel names.
    Uses chained AddPass nodes for flexible pass assembly.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "rgb": ("IMAGE",),
                "alpha": ("IMAGE",),
                "output_name": ("STRING", {"default": "render"}),
                "output_path": ("STRING", {"default": "output"}),
                "start_frame": ("INT", {"default": 1001, "min": 0, "max": 999999}),
                "colorspace": (["sRGB", "linear"], {"default": "sRGB"}),
            },
            "optional": {
                "passes": ("PASS_CHAIN",),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_info",)
    FUNCTION = "export_exr"
    CATEGORY = "image/export"
    OUTPUT_NODE = True

    def export_exr(self, rgb, alpha, output_name, output_path, start_frame, colorspace, passes=None):
        """
        Export multi-channel EXR sequence from render passes.
        """
        
        # Create output directory if it doesn't exist
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Collect all passes with their names
        all_passes = {
            "rgb": rgb,
            "alpha": alpha,
        }
        
        # Add passes from the chain
        if passes is not None:
            all_passes.update(passes)
        
        # Get batch size (number of frames)
        batch_size = rgb.shape[0]
        
        # Validate all passes have the same batch size
        for pass_name, pass_data in all_passes.items():
            if pass_data.shape[0] != batch_size:
                raise ValueError(f"Pass '{pass_name}' has different batch size: {pass_data.shape[0]} vs {batch_size}")
        
        # Process each frame in the batch
        exported_files = []
        for frame_idx in range(batch_size):
            frame_number = start_frame + frame_idx
            output_filename = f"{output_name}.{frame_number:04d}.exr"
            output_filepath = output_dir / output_filename
            
            # Export this frame
            self._export_single_frame(all_passes, frame_idx, output_filepath, colorspace)
            exported_files.append(str(output_filepath))
        
        # Return info about exported files
        info = f"Exported {len(exported_files)} frames:\n"
        info += f"Range: {start_frame} - {start_frame + batch_size - 1}\n"
        info += f"Location: {output_dir}\n"
        info += f"Colorspace: {colorspace}\n"
        info += f"Passes: {', '.join(all_passes.keys())}"
        
        print(info)
        return (info,)
    
    def _export_single_frame(self, passes, frame_idx, output_filepath, colorspace):
        """
        Export a single frame with all passes to an EXR file.
        """
        
        # Get image dimensions from beauty pass
        first_pass = next(iter(passes.values()))
        height, width = first_pass.shape[1], first_pass.shape[2]
        
        # Create EXR header
        header = OpenEXR.Header(width, height)
        
        # Set colorspace attribute in the header
        # OpenEXR uses chromaticities attribute to define colorspace
        if colorspace == "sRGB":
            # sRGB chromaticities (Rec.709 primaries with D65 white point)
            header['chromaticities'] = Imath.Chromaticities(
                Imath.V2f(0.64, 0.33),   # red
                Imath.V2f(0.30, 0.60),   # green
                Imath.V2f(0.15, 0.06),   # blue
                Imath.V2f(0.3127, 0.3290) # white (D65)
            )
        # For linear, we don't set chromaticities (or use scene-linear default)
        
        # Prepare channels dictionary
        channels = {}
        channel_names = []
        
        for pass_name, pass_data in passes.items():
            # Get the frame from the batch
            frame = pass_data[frame_idx]  # Shape: [H, W, C]
            
            # Convert from torch tensor to numpy
            if isinstance(frame, torch.Tensor):
                frame = frame.cpu().numpy()
            
            # Ensure float32
            frame = frame.astype(np.float32)
            
            # ComfyUI images are [H, W, C], we need to split channels
            num_channels = frame.shape[2]
            
            # Standard channel naming
            if num_channels == 1:
                # Single channel (like depth or single matte)
                if pass_name == "depth":
                    channel_suffix = ["Z"]
                elif pass_name == "alpha":
                    # Alpha pass uses just "A" with no prefix
                    channel_suffix = ["A"]
                elif pass_name.startswith("matte"):
                    # Mattes use .alpha instead of .A
                    channel_suffix = ["alpha"]
                else:
                    channel_suffix = ["A"]
            elif num_channels == 3:
                channel_suffix = ["R", "G", "B"]
            elif num_channels == 4:
                channel_suffix = ["R", "G", "B", "A"]
            else:
                # Fallback for unusual channel counts
                channel_suffix = [str(i) for i in range(num_channels)]
            
            # Add each channel to the EXR
            for ch_idx, suffix in enumerate(channel_suffix):
                # RGB and alpha passes get no prefix, just the channel names
                if pass_name in ["rgb", "alpha"]:
                    channel_name = suffix
                else:
                    channel_name = f"{pass_name}.{suffix}"
                    
                channel_names.append(channel_name)
                
                # Extract channel data and convert to bytes
                channel_data = frame[:, :, ch_idx]
                channels[channel_name] = channel_data.astype(np.float32).tobytes()
        
        # Set up channel types in header
        channel_dict = {}
        for name in channel_names:
            channel_dict[name] = Imath.Channel(Imath.PixelType(Imath.PixelType.FLOAT))
        header['channels'] = channel_dict
        
        # Write the EXR file
        exr_file = OpenEXR.OutputFile(str(output_filepath), header)
        exr_file.writePixels(channels)
        exr_file.close()
        
        print(f"Exported: {output_filepath}")


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "MultiPassEXRExporter": MultiPassEXRExporter,
    "AddPass": AddPass,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiPassEXRExporter": "Multi-Pass EXR Exporter",
    "AddPass": "Add Pass",
}

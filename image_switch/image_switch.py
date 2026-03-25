"""
ImageSwitch - A Nuke-style Switch node for ComfyUI
Connects multiple image inputs and passes through the one selected by 'which'.
- 'which' is zero-indexed (0 = first input)
- 'which' widget can be converted to an INT input socket
- 'num_inputs' controls how many image sockets are shown (updated via JS button)
- 'use_masks' enables a corresponding mask_N socket for each image_N
- Outputs IMAGE, MASK, and STRING (title of the upstream node on the selected input)
- JS serializes all upstream titles as JSON; Python picks the active one by 'which'
- mask output is None if not connected; string output is "" if not connected
"""

import json

MAX_INPUTS = 32


class ImageSwitch:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(MAX_INPUTS):
            optional[f"image_{i}"] = ("IMAGE",)
            optional[f"mask_{i}"] = ("MASK",)
        return {
            "required": {
                "which": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": MAX_INPUTS - 1,
                    "step": 1,
                    "display": "number"
                }),
                "num_inputs": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": MAX_INPUTS,
                    "step": 1,
                    "display": "number"
                }),
                "use_masks": ("BOOLEAN", {"default": False}),
                # Written by JS before execution — JSON array of all upstream titles
                "upstream_titles": ("STRING", {"default": "[]"}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "node_name")
    FUNCTION = "switch"
    CATEGORY = "image/utils"

    def switch(self, which, num_inputs, use_masks, upstream_titles, **kwargs):
        # Resolve image, with fallback to nearest connected input
        image = kwargs.get(f"image_{which}")
        resolved_index = which

        if image is None:
            for i in range(which - 1, -1, -1):
                fallback = kwargs.get(f"image_{i}")
                if fallback is not None:
                    print(f"[ImageSwitch] Input {which} not connected, falling back to input {i}")
                    image = fallback
                    resolved_index = i
                    break
            if image is None:
                raise ValueError(
                    f"[ImageSwitch] 'which' is set to {which} but no inputs are connected."
                )

        # Resolve mask
        mask = kwargs.get(f"mask_{resolved_index}") if use_masks else None

        # Pick the upstream title for the resolved index
        try:
            titles = json.loads(upstream_titles)
        except Exception:
            titles = []

        node_name = titles[resolved_index] if resolved_index < len(titles) else ""

        return (image, mask, node_name)


NODE_CLASS_MAPPINGS = {
    "ImageSwitch": ImageSwitch,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ImageSwitch": "Switch/Which",
}

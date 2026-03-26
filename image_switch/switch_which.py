"""
SwitchWhich + SwitchWhichInfo — Nuke-style Switch nodes for ComfyUI.

SwitchWhich:
- Accepts any input type via wildcard '*'
- IMAGE inputs automatically get a paired mask_N slot
- Outputs: data (matched type), mask (MASK | None)
- JS patches output type to match the active input

SwitchWhichInfo:
- Connect to a SwitchWhich node's data output
- Outputs: node_name (STRING) — title of the upstream node on the active input
- Reads metadata serialized by JS into the SwitchWhich node
"""

import json

MAX_INPUTS = 32


class SwitchWhich:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(MAX_INPUTS):
            optional[f"input_{i}"] = ("*",)
            optional[f"mask_{i}"]  = ("MASK",)
        return {
            "required": {
                "which": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": MAX_INPUTS - 1,
                    "step": 1,
                    "display": "number",
                }),
                "num_inputs": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": MAX_INPUTS,
                    "step": 1,
                    "display": "number",
                }),
                # Written by JS — JSON array of booleans, true = that slot is IMAGE type
                "slot_is_image":   ("STRING", {"default": "[]"}),
                # Written by JS — JSON array of all upstream node titles
                "upstream_titles": ("STRING", {"default": "[]"}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("*",    "MASK",  "STRING")
    RETURN_NAMES = ("data", "mask",  "_metadata")
    FUNCTION     = "switch"
    CATEGORY     = "utils"

    def switch(self, which, num_inputs, slot_is_image, upstream_titles, **kwargs):
        # Resolve data, with fallback to nearest connected input
        data = kwargs.get(f"input_{which}")
        resolved_index = which

        if data is None:
            for i in range(which - 1, -1, -1):
                fallback = kwargs.get(f"input_{i}")
                if fallback is not None:
                    print(f"[SwitchWhich] Input {which} not connected, falling back to input {i}")
                    data = fallback
                    resolved_index = i
                    break
            if data is None:
                raise ValueError(
                    f"[SwitchWhich] 'which' is set to {which} but no inputs are connected."
                )

        # Resolve mask — only for IMAGE slots
        try:
            is_image_flags = json.loads(slot_is_image)
        except Exception:
            is_image_flags = []

        slot_is_img = (
            resolved_index < len(is_image_flags) and is_image_flags[resolved_index]
        )
        mask = kwargs.get(f"mask_{resolved_index}") if slot_is_img else None

        # Pass metadata blob to Info node (JSON string)
        metadata = json.dumps({
            "titles":   json.loads(upstream_titles) if upstream_titles else [],
            "resolved": resolved_index,
        })

        return (data, mask, metadata)


class SwitchWhichInfo:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "_metadata": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES  = ("STRING",)
    RETURN_NAMES  = ("node_name",)
    FUNCTION      = "read_info"
    CATEGORY      = "utils"

    def read_info(self, _metadata):
        try:
            data     = json.loads(_metadata)
            titles   = data.get("titles", [])
            resolved = data.get("resolved", 0)
            name     = titles[resolved] if resolved < len(titles) else ""
        except Exception:
            name = ""
        return (name,)


NODE_CLASS_MAPPINGS = {
    "SwitchWhich":     SwitchWhich,
    "SwitchWhichInfo": SwitchWhichInfo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SwitchWhich":     "Switch/Which",
    "SwitchWhichInfo": "Switch/Which Info",
}

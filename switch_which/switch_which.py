"""
SwitchWhich + SwitchWhichInfo — Nuke-style Switch nodes for ComfyUI.

SwitchWhich:
- Accepts any input type via wildcard '*'
- IMAGE inputs automatically get a paired mask_N slot
- Only evaluates the active input (lazy evaluation via check_lazy_status)
- Outputs: data (matched type), mask (MASK | None), _metadata (STRING, internal)

SwitchWhichInfo:
- Connect to a SwitchWhich node's _metadata output
- Outputs: node_name (STRING) — title of the upstream node on the active input
"""

import json

MAX_INPUTS = 32


class SwitchWhich:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {}
        for i in range(MAX_INPUTS):
            optional[f"input_{i}"] = ("*", {"lazy": True})
            optional[f"mask_{i}"]  = ("MASK", {"lazy": True})
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
                "slot_is_image":   ("STRING", {"default": "[]"}),
                "upstream_titles": ("STRING", {"default": "[]"}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("*",    "MASK",  "STRING")
    RETURN_NAMES = ("data", "mask",  "_metadata")
    FUNCTION     = "switch"
    CATEGORY     = "utils"

    def check_lazy_status(self, which, num_inputs, slot_is_image, upstream_titles, **kwargs):
        """
        Tell ComfyUI which inputs we actually need evaluated.
        Only request input_which (and its mask if IMAGE).
        If that input isn't connected, walk back to find the nearest connected one.
        """
        needed = []

        # Find the first connected input at or before 'which'
        resolved = None
        for i in range(which, -1, -1):
            key = f"input_{i}"
            # kwargs contains None for lazy inputs not yet evaluated,
            # and is absent entirely for unconnected inputs.
            # We need to check if the slot is wired at all.
            if key in kwargs:
                resolved = i
                break

        if resolved is not None:
            needed.append(f"input_{resolved}")

            # Only request mask if this slot is IMAGE type
            try:
                is_image_flags = json.loads(slot_is_image)
            except Exception:
                is_image_flags = []

            if resolved < len(is_image_flags) and is_image_flags[resolved]:
                mask_key = f"mask_{resolved}"
                if mask_key in kwargs:
                    needed.append(mask_key)

        return needed

    def switch(self, which, num_inputs, slot_is_image, upstream_titles, **kwargs):
        # Resolve data, falling back if which isn't connected
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

        # Pack metadata for the Info node
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

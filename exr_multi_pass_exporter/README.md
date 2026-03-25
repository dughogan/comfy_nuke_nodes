# Multi-Pass EXR Exporter for ComfyUI

Export multiple render passes (beauty, mattes, depth, etc.) into multi-channel EXR sequences. Simple chaining system lets you add as many passes as you need.

## Installation (2 Steps!)

### 1. Copy the File
Copy `__init__.py` to your ComfyUI custom nodes directory:
```
ComfyUI/custom_nodes/exr_multi_pass_exporter/__init__.py
```

Create the `exr_multi_pass_exporter` folder if it doesn't exist.

### 2. Restart ComfyUI
**That's it!** The node will automatically install its dependencies (OpenEXR, Imath) on first load.

After restarting, you'll find two new nodes under:
- **Add Node → image → export → Multi-Pass EXR Exporter**
- **Add Node → image → export → Add Pass**

> **Note**: If auto-install fails, you can manually install dependencies by opening ComfyUI's terminal and running:
> ```bash
> pip install OpenEXR Imath
> ```
> Then restart ComfyUI again.

---

## Quick Start

### Basic Setup (RGB + Alpha only):
1. Add "Multi-Pass EXR Exporter" node
2. Connect your RGB image to `rgb` input
3. Connect your alpha/matte to `alpha` input
4. Set output settings (name, path, frame number)
5. Run!

### Adding More Passes:
Use "Add Pass" nodes to add depth, additional mattes, or other passes:

```
[Load RGB] → rgb input ─┐
[Load Alpha] → alpha input ─┤
                            │
[Load Depth] → [Add Pass: "depth"] ─┐
                                    │
[Load MatteB] → [Add Pass: "matteB"] ┤
                                     │
                                     └→ passes input
                                        
                        [Multi-Pass EXR Exporter]
                        - output_name: "render"
                        - output_path: "output"
                        - start_frame: 1001
```

**Chain additional passes together**, then connect the final chain to the exporter's `passes` input.

---

## The Two Nodes

### Multi-Pass EXR Exporter
Main export node with these inputs:
- `rgb` - Your RGB render (required)
- `alpha` - Your alpha/matte channel (required)
- `passes` - Chain of additional passes from Add Pass nodes (optional)
- `output_name` - Base filename (e.g., "render")
- `output_path` - Where to save (e.g., "output")
- `start_frame` - Starting frame number (default: 1001)
- `colorspace` - sRGB or linear (default: sRGB)

### Add Pass
Chainable node for adding passes:
- `image` - The pass image to add
- `pass_name` - Name for this pass (e.g., "depth", "matteB")
- `passes` - Connect previous Add Pass here (optional)

Chain as many Add Pass nodes as you need!

---

## Output Format

**Files**: `{output_name}.{frame_number}.exr`
- Example: `render.1001.exr`, `render.1002.exr`, etc.

**Channels**: Each pass becomes channels in the EXR:
- RGB → `R`, `G`, `B` (no prefix)
- Alpha → `A` (no prefix)
- Depth → `depth.Z`
- MatteB → `matteB.alpha`
- Cleanplate → `cleanplate.R`, `cleanplate.G`, `cleanplate.B`
- Custom → `{pass_name}.{channel}`

**Smart naming**:
- Pass names starting with "matte" → `.alpha` suffix
- Pass name "depth" → `.Z` suffix
- Everything else → `.R`, `.G`, `.B`, `.A` suffixes

---

## Features

✅ Clean chaining system - add unlimited passes  
✅ Custom pass names for each  
✅ Multi-channel EXR output  
✅ Preserved channel names  
✅ sRGB or linear colorspace  
✅ Batch processing for sequences  
✅ Flexible frame numbering  

---

## Troubleshooting

### "No module named 'OpenEXR'"
The node should auto-install dependencies on first load. If it didn't work:

**Solution**: Open ComfyUI terminal and run:
```bash
pip install OpenEXR Imath
```
Then restart ComfyUI.

If you're using ComfyUI portable, you may need to find the embedded Python:
```bash
# Windows
C:\path\to\ComfyUI\python_embeded\python.exe -m pip install OpenEXR Imath

# Linux/Mac  
/path/to/ComfyUI/python/bin/pip install OpenEXR Imath
```

### "Different batch size error"
All passes must have the same number of frames. Make sure all your loaded images have matching frame counts.

### Node doesn't appear after restart
Check the ComfyUI console for errors. Verify the file is named `__init__.py` and is in the `custom_nodes/exr_multi_pass_exporter/` folder.

### Permission errors when saving
Make sure the `output_path` directory exists and is writable. Use absolute paths if relative paths cause issues.

---

## Tips

💡 **Colorspace**: Use "linear" for VFX workflows, "sRGB" for most other cases  
💡 **Frame padding**: Uses 4-digit padding automatically (1001, 1002, etc.)  
💡 **Pass naming**: Name passes clearly - they become your EXR channel prefixes  
💡 **Batch processing**: Load multiple frames and they'll export as a sequence  
💡 **Resolution**: All passes must have identical dimensions  

---

## Example Workflow

Full example with 5 passes:

```
[Load RGB] → rgb input ─┐
[Load Alpha] → alpha input ─┤
                            │
                            │
[Load Depth] → [Add Pass: "depth"] ─┐
                                    │
[Load MatteB] → [Add Pass: "matteB"] ┤
                                     │
[Load Cleanplate] → [Add Pass: "cleanplate"] ┤
                                              │
                                              └→ passes input
                                                 
                        [Multi-Pass EXR Exporter]
                        - output_name: "shot_010"  
                        - output_path: "renders"
                        - start_frame: 1001
                        - colorspace: "sRGB"
                        
                        Output ↓
                        renders/shot_010.1001.exr
                        renders/shot_010.1002.exr
                        ...
```

Each EXR contains:
- `R`, `G`, `B` (from rgb input)
- `A` (from alpha input)
- `depth.Z` (from Add Pass)
- `matteB.alpha` (from Add Pass)
- `cleanplate.R`, `cleanplate.G`, `cleanplate.B` (from Add Pass)

---

## Requirements

- ComfyUI
- Python packages: OpenEXR, Imath
- PyTorch, NumPy (included with ComfyUI)

---

## Support

Having issues? Check:
1. Dependencies installed correctly (`pip install OpenEXR Imath`)
2. ComfyUI restarted after installation
3. File named `__init__.py` in the right folder
4. All passes have matching resolution and frame count
5. Output directory has write permissions

---

**Created for flexible, professional multi-pass EXR export in ComfyUI**

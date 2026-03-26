import { app } from "../../scripts/app.js";

const MAX_INPUTS = 32;

app.registerExtension({
    name: "SwitchWhich",

    async beforeRegisterNodeDef(nodeType, nodeData) {

        // ── SwitchWhich ──────────────────────────────────────────────────────
        if (nodeData.name === "SwitchWhich") {

            nodeType.prototype.onConnectInput = function () { return true; };

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);

                hideWidget(this, "slot_is_image");
                hideWidget(this, "upstream_titles");
                // _metadata output is internal — hide the output label
                if (this.outputs?.[2]) this.outputs[2].label = "";

                this.addWidget("button", "Update Inputs", null, () => {
                    const numWidget = this.widgets.find(w => w.name === "num_inputs");
                    if (!numWidget) return;
                    updateInputSockets(this, numWidget.value);
                }, { serialize: false });

                const numWidget = this.widgets.find(w => w.name === "num_inputs");
                updateInputSockets(this, numWidget?.value ?? 2);
            };

            const onConnectionsChange = nodeType.prototype.onConnectionsChange;
            nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
                onConnectionsChange?.apply(this, arguments);
                reconcileMaskSlots(this);
                patchOutputType(this);
                writeAllMetadata(this);
            };

            const onWidgetChanged = nodeType.prototype.onWidgetChanged;
            nodeType.prototype.onWidgetChanged = function (name, value) {
                onWidgetChanged?.apply(this, arguments);
                if (name === "which") {
                    patchOutputType(this);
                    writeAllMetadata(this);
                }
            };

            const onSerialize = nodeType.prototype.onSerialize;
            nodeType.prototype.onSerialize = function (data) {
                onSerialize?.apply(this, arguments);
                writeAllMetadata(this);
                data.num_inputs = this.widgets.find(w => w.name === "num_inputs")?.value ?? 2;
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function (data) {
                onConfigure?.apply(this, arguments);
                const count = data.num_inputs ?? 2;
                const numWidget = this.widgets.find(w => w.name === "num_inputs");
                if (numWidget) numWidget.value = count;
                updateInputSockets(this, count);
                setTimeout(() => {
                    reconcileMaskSlots(this);
                    patchOutputType(this);
                    writeAllMetadata(this);
                }, 50);
            };
        }

        // ── SwitchWhichInfo ──────────────────────────────────────────────────
        if (nodeData.name === "SwitchWhichInfo") {
            // Hide the raw _metadata input label so it just looks like a connector
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);
                const slot = this.inputs?.find(i => i.name === "_metadata");
                if (slot) slot.label = "switch";
            };
        }
    },

    beforeQueuePrompt() {
        for (const node of app.graph._nodes) {
            if (node.type === "SwitchWhich") {
                reconcileMaskSlots(node);
                patchOutputType(node);
                writeAllMetadata(node);
            }
        }
    },
});

// ── Output type patching ─────────────────────────────────────────────────────
function patchOutputType(node) {
    const which = node.widgets?.find(w => w.name === "which")?.value ?? 0;
    const resolvedType = getInputType(node, `input_${which}`) ?? "*";

    if (node.outputs?.[0]) {
        node.outputs[0].type  = resolvedType;
        node.outputs[0].label = resolvedType === "*" ? "data" : resolvedType;
    }
    node.setDirtyCanvas(true, true);
}

// ── Mask slot reconciliation — IMAGE inputs only ──────────────────────────────
function reconcileMaskSlots(node) {
    const count = node.widgets?.find(w => w.name === "num_inputs")?.value ?? MAX_INPUTS;

    for (let i = 0; i < count; i++) {
        const type      = getInputType(node, `input_${i}`);
        const isImage   = type === "IMAGE";
        const maskExists = node.inputs?.some(inp => inp.name === `mask_${i}`);

        if (isImage && !maskExists) {
            node.addInput(`mask_${i}`, "MASK");
            // Slot directly after its image input
            const inputIdx = node.inputs.findIndex(inp => inp.name === `input_${i}`);
            const maskIdx  = node.inputs.findIndex(inp => inp.name === `mask_${i}`);
            if (maskIdx !== inputIdx + 1) {
                const [slot] = node.inputs.splice(maskIdx, 1);
                node.inputs.splice(inputIdx + 1, 0, slot);
            }
        } else if (!isImage && maskExists) {
            removeNamedInput(node, `mask_${i}`);
        }
    }
    node.setDirtyCanvas(true, true);
}

// ── Metadata serialization ───────────────────────────────────────────────────
function writeAllMetadata(node) {
    const titlesWidget  = node.widgets?.find(w => w.name === "upstream_titles");
    const isImageWidget = node.widgets?.find(w => w.name === "slot_is_image");
    if (!titlesWidget || !isImageWidget) return;

    const count  = node.widgets?.find(w => w.name === "num_inputs")?.value ?? MAX_INPUTS;
    const titles = [];
    const isImgs = [];

    for (let i = 0; i < count; i++) {
        const inputSlot = node.inputs?.findIndex(inp => inp.name === `input_${i}`);
        if (inputSlot == null || inputSlot === -1) { titles.push(""); isImgs.push(false); continue; }
        const linkId = node.inputs[inputSlot].link;
        if (linkId == null) { titles.push(""); isImgs.push(false); continue; }
        const link = node.graph.links[linkId];
        if (!link) { titles.push(""); isImgs.push(false); continue; }
        const upstream = node.graph.getNodeById(link.origin_id);
        const slotType = upstream?.outputs?.[link.origin_slot]?.type ?? null;
        titles.push(upstream?.title ?? upstream?.type ?? "");
        isImgs.push(slotType === "IMAGE");
    }

    titlesWidget.value  = JSON.stringify(titles);
    isImageWidget.value = JSON.stringify(isImgs);
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function getInputType(node, inputName) {
    const slot = node.inputs?.findIndex(i => i.name === inputName);
    if (slot == null || slot === -1) return null;
    const linkId = node.inputs[slot].link;
    if (linkId == null) return null;
    const link = node.graph.links[linkId];
    if (!link) return null;
    const upstream = node.graph.getNodeById(link.origin_id);
    return upstream?.outputs?.[link.origin_slot]?.type ?? null;
}

function updateInputSockets(node, count) {
    count = Math.max(1, Math.min(MAX_INPUTS, count));
    const existing = node.inputs?.filter(i => i.name.startsWith("input_")).length ?? 0;

    if (count > existing) {
        for (let i = existing; i < count; i++) node.addInput(`input_${i}`, "*");
    } else if (count < existing) {
        for (let i = existing - 1; i >= count; i--) {
            removeNamedInput(node, `mask_${i}`);
            removeNamedInput(node, `input_${i}`);
        }
    }

    const whichWidget = node.widgets?.find(w => w.name === "which");
    if (whichWidget) {
        whichWidget.options.max = count - 1;
        if (whichWidget.value >= count) whichWidget.value = count - 1;
    }
    node.setDirtyCanvas(true, true);
}

function removeNamedInput(node, name) {
    const idx = node.inputs?.findIndex(i => i.name === name);
    if (idx == null || idx === -1) return;
    if (node.inputs[idx].link != null) node.graph.removeLink(node.inputs[idx].link);
    node.removeInput(idx);
}

function hideWidget(node, name) {
    const w = node.widgets?.find(w => w.name === name);
    if (!w) return;
    w.type = "hidden";
    w.computeSize = () => [0, -4];
}

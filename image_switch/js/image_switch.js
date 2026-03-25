import { app } from "../../scripts/app.js";

const MAX_INPUTS = 32;

app.registerExtension({
    name: "ImageSwitch",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ImageSwitch") return;

        // --- Node creation ---
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);

            // Hide the upstream_titles widget — internal plumbing only
            const titlesWidget = this.widgets.find(w => w.name === "upstream_titles");
            if (titlesWidget) {
                titlesWidget.type = "hidden";
                titlesWidget.computeSize = () => [0, -4];
            }

            this.addWidget("button", "Update Inputs", null, () => {
                const numWidget  = this.widgets.find(w => w.name === "num_inputs");
                const maskWidget = this.widgets.find(w => w.name === "use_masks");
                if (!numWidget) return;
                updateInputSockets(this, numWidget.value, maskWidget?.value ?? false);
            }, { serialize: false });

            const numWidget  = this.widgets.find(w => w.name === "num_inputs");
            const maskWidget = this.widgets.find(w => w.name === "use_masks");
            updateInputSockets(this, numWidget?.value ?? 2, maskWidget?.value ?? false);
        };

        // --- Serialization: always snapshot all upstream titles before prompt is sent ---
        const onSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onSerialize = function (data) {
            onSerialize?.apply(this, arguments);
            writeAllUpstreamTitles(this);
            data.num_inputs = this.widgets.find(w => w.name === "num_inputs")?.value ?? 2;
            data.use_masks  = this.widgets.find(w => w.name === "use_masks")?.value  ?? false;
        };

        // --- Deserialization ---
        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (data) {
            onConfigure?.apply(this, arguments);
            const count    = data.num_inputs ?? 2;
            const useMasks = data.use_masks  ?? false;

            const numWidget  = this.widgets.find(w => w.name === "num_inputs");
            const maskWidget = this.widgets.find(w => w.name === "use_masks");
            if (numWidget)  numWidget.value  = count;
            if (maskWidget) maskWidget.value = useMasks;

            updateInputSockets(this, count, useMasks);
        };
    },

    // Last chance before prompt is queued — covers the socket-driven 'which' case
    // by snapshotting ALL input titles; Python selects the right one at runtime
    beforeQueuePrompt() {
        for (const node of app.graph._nodes) {
            if (node.type === "ImageSwitch") {
                writeAllUpstreamTitles(node);
            }
        }
    },
});

/**
 * Walk every image_N input, resolve its upstream node title, and write the
 * full array as JSON into the hidden upstream_titles widget.
 * Python picks the correct entry using the runtime value of 'which'.
 */
function writeAllUpstreamTitles(node) {
    const titlesWidget = node.widgets?.find(w => w.name === "upstream_titles");
    const numWidget    = node.widgets?.find(w => w.name === "num_inputs");
    if (!titlesWidget) return;

    const count = numWidget?.value ?? MAX_INPUTS;
    const titles = [];

    for (let i = 0; i < count; i++) {
        const inputSlot = node.inputs?.findIndex(inp => inp.name === `image_${i}`);
        if (inputSlot == null || inputSlot === -1) {
            titles.push("");
            continue;
        }

        const linkId = node.inputs[inputSlot].link;
        if (linkId == null) {
            titles.push("");
            continue;
        }

        const link = node.graph.links[linkId];
        if (!link) {
            titles.push("");
            continue;
        }

        const upstreamNode = node.graph.getNodeById(link.origin_id);
        titles.push(upstreamNode?.title ?? upstreamNode?.type ?? "");
    }

    titlesWidget.value = JSON.stringify(titles);
}

/**
 * Add or remove image_N (and optionally mask_N) input sockets.
 */
function updateInputSockets(node, count, useMasks) {
    count = Math.max(1, Math.min(MAX_INPUTS, count));

    const existingInputs = node.inputs ? [...node.inputs] : [];
    const imageSlots = existingInputs.filter(i => i.name.startsWith("image_")).length;
    const maskSlots  = existingInputs.filter(i => i.name.startsWith("mask_")).length;

    // Reconcile image sockets
    if (count > imageSlots) {
        for (let i = imageSlots; i < count; i++) node.addInput(`image_${i}`, "IMAGE");
    } else if (count < imageSlots) {
        for (let i = imageSlots - 1; i >= count; i--) removeNamedInput(node, `image_${i}`);
    }

    // Reconcile mask sockets
    if (useMasks) {
        if (count > maskSlots) {
            for (let i = maskSlots; i < count; i++) node.addInput(`mask_${i}`, "MASK");
        } else if (count < maskSlots) {
            for (let i = maskSlots - 1; i >= count; i--) removeNamedInput(node, `mask_${i}`);
        }
    } else {
        for (let i = maskSlots - 1; i >= 0; i--) removeNamedInput(node, `mask_${i}`);
    }

    // Clamp 'which' max to count - 1
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

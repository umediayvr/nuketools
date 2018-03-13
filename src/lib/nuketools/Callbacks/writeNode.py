import nuke

def onWriteNodeUpdate(node=None, knob=None):
    """
    Triggered when a knob in the write node is changed.
    """
    if not node:
        node = nuke.thisNode()

    if not knob:
        knob = nuke.thisKnob()

    # updating metadata knob to include all metadata
    if knob.name() == "file" and 'metadata' in node.knobs() and node['metadata'].enabled():
        metadataValue = 'all metadata'
        if metadataValue in node['metadata'].values():
            node['metadata'].setValue(metadataValue)


# registering callbacks
nuke.addKnobChanged(onWriteNodeUpdate, nodeClass="Write")

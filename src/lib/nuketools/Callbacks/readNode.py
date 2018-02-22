import re
import os
import nuke

def onCreateReadNode():
    """
    Triggered when a read node is created.
    """
    node = nuke.thisNode()
    umediaTab = nuke.Tab_Knob('umedia', 'UMedia')
    variations = nuke.Enumeration_Knob('uvariations', 'Variations', [])
    node.addKnob(umediaTab)
    node.addKnob(variations)

    # forcing to update the list of variations
    onReadNodeUpdate(node, node['file'])

def onReadNodeUpdate(node=None, knob=None):
    """
    Triggered when a knob in the read node is changed.
    """
    if not node:
        node = nuke.thisNode()

    if not knob:
        knob = nuke.thisKnob()

    # updating the list of variations
    if knob.name() == "file" and 'uvariations' in node.knobs():
        variations = []
        currentFilePath = node['file'].getValue()
        currentVariationDiretory = os.path.dirname(currentFilePath)
        variationsDirectory = os.path.dirname(currentVariationDiretory)

        if currentVariationDiretory and os.path.exists(variationsDirectory):
            for variationName in os.listdir(variationsDirectory):

                # the variation should start with a resolution as prefix (1920x1080)
                if not re.match('^[0-9]+[x|X][0-9]+', variationName):
                    continue

                # making sure it's a directory
                if os.path.isdir(os.path.join(variationsDirectory, variationName)):
                    variations.append(variationName)

        node['uvariations'].setValues(variations)
        if variations:
            node['uvariations'].setValue(os.path.basename(currentVariationDiretory))

    # updating current variation
    elif knob.name() == "uvariations":
        currentFile = os.path.basename(node['file'].value())
        variationsBaseDirectory = os.path.dirname(os.path.dirname(node['file'].value()))
        node['file'].setValue(os.path.join(variationsBaseDirectory, knob.value(), currentFile))


# registering callbacks
nuke.addKnobChanged(onReadNodeUpdate, nodeClass="Read")
nuke.addOnCreate(onCreateReadNode, nodeClass="Read")

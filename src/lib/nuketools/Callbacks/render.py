import nuke
import json
from ..App.NukeHook import NukeHook
from fnmatch import fnmatch


# \TODO: Make the header of the metadata into Umedia e.g. Umedia/*
__metadataConvention = 'exr/nuke/*Cdl'


def beforeRender():
    """
    Triggered before a render is launch
    """
    checkMetadata()
    deNeutralize()


def afterRender():
    """
    Triggered after the render is done
    """
    deleteMetadataNode()


def deleteMetadataNode():
    """
    Delete the node created to add the metadata if exists
    """
    metadataNode = nuke.toNode('AddMetadataBR')
    if not metadataNode:
        return
    nuke.delete(metadataNode)


def checkMetadata():
    """
    Checks if the metadata exist in the write node, if not, it try to find it in any read node and putted back
    before the write node
    """
    writeNode = nuke.thisNode()
    xposWriteNode = writeNode.xpos()
    yposWriteNode = writeNode.ypos()

    for metadataKey in writeNode.metadata().keys():
        if fnmatch(metadataKey, __metadataConvention):
            return

    value = None
    name = None
    for readNode in NukeHook.queryAllNodes('Read'):
        for metadataKey in readNode.metadata().keys():
            if fnmatch(metadataKey, __metadataConvention):
                value = readNode.metadata()[metadataKey]
                name = metadataKey.split('/')[-1]
                break

    if value is None or name is None:
        return

    metadataNode = nuke.createNode('ModifyMetaData')
    metadataNode.setName('AddMetadataBR')
    metadataNode.setXYpos(xposWriteNode, yposWriteNode - 40)
    metadataNode.knob('metadata').fromScript('{' + "set {name}".format(name=name) + " \"{}\"".format(value.replace('"', '\\"')) + '}')
    connectedNode = writeNode.input(0)
    metadataNode.setInput(0, connectedNode)
    writeNode.setInput(0, metadataNode)


def deNeutralize():
    """
    checks for the "DeNeutralize" node first to make sure the callback is coming from a Media delivery template,
    then get the information of the metadata and add the values to the "DeNeutralize" node.
    """
    value = None
    cdlNeutralNode = nuke.toNode('DeNeutralize')
    # Checks if the node exists
    if not cdlNeutralNode:
        return

    for readNode in NukeHook.queryAllNodes('Read'):
        for metadataKey in readNode.metadata().keys():
            if fnmatch(metadataKey, __metadataConvention):
                value = readNode.metadata()[metadataKey]
                break

    if not value:
        return

    # The value of the cdl neutral are serialized in a json format
    cdlValues = json.loads(value)
    cdlNeutralNode['slope'].setValue(cdlValues['slope'])
    cdlNeutralNode['offset'].setValue(cdlValues['offset'])
    cdlNeutralNode['power'].setValue(cdlValues['power'])
    cdlNeutralNode['saturation'].setValue(cdlValues['saturation'])


# registering callbacks
nuke.addBeforeRender(beforeRender, nodeClass='Write')
nuke.addAfterRender(afterRender, nodeClass='Write')

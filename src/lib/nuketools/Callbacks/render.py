"""Render callbacks."""
import nuke
from ..App.NukeHook import NukeHook
from fnmatch import fnmatch


# \TODO: Make the header of the metadata into Umedia e.g. Umedia/*
__metadataConvention = 'exr/nuke/*Cdl'
__modifyMetadataName = '__AddMetadataBR'


def beforeRender():
    """Triggered before a render is launch."""
    writeNode = nuke.thisNode()
    if not checkMetadata(writeNode):
        addMetadata(writeNode)


def afterRender():
    """Triggered after the render is done."""
    deleteMetadataNode()


def deleteMetadataNode():
    """Delete the node created to add the metadata if exists."""
    metadataNode = nuke.toNode(__modifyMetadataName)
    if not metadataNode:
        return
    nuke.delete(metadataNode)


def addMetadata(writeNode):
    """
    Add the metadata before it render.

    Create a node to add the metadata found in a write node.
    :parm writeNode: The curernt write node
    :type writeNode: nuke.Node
    """
    xposWriteNode = writeNode.xpos()
    yposWriteNode = writeNode.ypos()
    value = None
    name = None
    for readNode in NukeHook.queryAllNodes('Read'):
        metadata = readNode.metadata()
        for metadataKey in metadata.keys():
            if fnmatch(metadataKey, __metadataConvention):
                value = metadata[metadataKey]
                name = metadataKey.split('/')[-1]
                break

    if value is None or name is None:
        return

    metadataNode = nuke.createNode('ModifyMetaData')
    metadataNode.setName(__modifyMetadataName)
    metadataNode.setXYpos(xposWriteNode, yposWriteNode - 40)
    metadataNode.knob('metadata').fromScript('{' + "set {name}".format(name=name) + " \"{}\"".format(value.replace('"', '\\"')) + '}')
    connectedNode = writeNode.input(0)
    metadataNode.setInput(0, connectedNode)
    writeNode.setInput(0, metadataNode)


def checkMetadata(writeNode):
    """
    Check if the metadata exist in the write node.

    :parm writeNode: The curernt write node
    :type writeNode: nuke.Node
    :return foundMetadata: A flag that return if it found the metadata or not
    :rtype: boolean
    """
    foundMetadata = False

    for metadataKey in writeNode.metadata().keys():
        if fnmatch(metadataKey, __metadataConvention):
            foundMetadata = True

    return foundMetadata


# registering callbacks
nuke.addBeforeRender(beforeRender, nodeClass='Write')
nuke.addAfterRender(afterRender, nodeClass='Write')

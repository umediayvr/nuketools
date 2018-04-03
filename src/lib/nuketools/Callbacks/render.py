"""Render callbacks."""
import nuke
from fnmatch import fnmatch


# \TODO: Make the header of the metadata into Umedia e.g. Umedia/*
__metadataConvention = 'exr/nuke/*Cdl'
__modifyMetadataName = '__addMetadataBR'


def beforeRender():
    """Triggered before a render is launch."""
    writeNode = nuke.thisParent()
    if not hasMetadata(writeNode):
        addMetadata(writeNode)


def afterRender():
    """Triggered after the render is done."""
    deleteMetadataNode()


def deleteMetadataNode():
    """Delete the node created to add the metadata if exists."""
    writeNode = nuke.thisParent()
    metaNode = writeNode.input(0)

    if not metaNode.name() == __modifyMetadataName:
        return
    cropNode = metaNode.input(0)
    nuke.delete(metaNode)
    writeNode.setInput(0, cropNode)


def addMetadata(writeNode):
    """
    Add the metadata before it render.

    Create a node to add the metadata found in a write node.
    :parm writeNode: The curernt write node
    :type writeNode: nuke.Node
    """
    xposWriteNode = writeNode.xpos()
    yposWriteNode = writeNode.ypos()
    values = {}
    nodesFound = []
    traverseCompTree(writeNode, 'read', nodesFound)

    # check if the node have the information need it
    for node in nodesFound:
        metadata = node.metadata()
        if not metadata:
            continue
        for metadataKey in metadata.keys():
            if fnmatch(metadataKey, __metadataConvention):
                metavalue = metadata[metadataKey]
                metaname = metadataKey.split('/')[-1]
                if metaname not in values.keys():
                    values[metaname] = (metavalue, node.name())

                elif values[metaname][0] != metavalue:
                    raise ValueError(
                        'Can not determine a Neutral Cdl.\n{rNodeOne} and {rNodeTwo} have different Neutral Cdl values'.format(
                            rNodeOne=values[metaname][1],
                            rNodeTwo=node.name()
                        )
                    )
    if not values:
        return
    metadataNode = nuke.createNode('ModifyMetaData')
    metadataNode.setName(__modifyMetadataName)
    metadataNode.setXYpos(xposWriteNode, yposWriteNode - 40)
    for name, value in values.iteritems():
        metadataNode.knob('metadata').fromScript('{' + "set {name}".format(name=name) + " \"{}\"".format(value[0].replace('"', '\\"')) + '}')
    connectedNode = writeNode.input(0)
    metadataNode.setInput(0, connectedNode)
    writeNode.setInput(0, metadataNode)


def traverseCompTree(node, nodeType, nodesFound, nodeCache=[]):
    """
    Traverse the nuke node tree bottom to top from the a specific node.

    :param node: The node to start the recursion from.
    :type node: nuke.Node
    :param nodeType: The type of the node to be found in the node tree.
    :type nodeType: str
    :param nodesFound: The list to fill with the nodes found.
    :type nodesFound: list
    :param nodeCache: A list of nodes that has been revised.
    :type nodeCache: list
    """
    # Create a cache for nodes that have been process
    if node in nodeCache:
        return

    nodeCache.append(node)

    for i in range(node.inputs()):
        inputNode = node.input(i)
        if inputNode is None:
            continue
        if inputNode.Class() == nodeType.capitalize():
            nodesFound.append(inputNode)
        print 'NodesFound --->>>>>>> ', nodesFound
        traverseCompTree(inputNode, nodeType, nodesFound, nodeCache)


def hasMetadata(writeNode):
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

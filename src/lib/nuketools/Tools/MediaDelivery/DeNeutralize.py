"""Specfic functions for the media delivery process."""
import json
import nuke
from fnmatch import fnmatch
from ...App.NukeHook import NukeHook


def deNeutralize():
    """
    Set the "Deneutralize" node.

    Checks for the "DeNeutralize" node first to make sure the callback is coming from a Media delivery template,
    then get the information of the metadata and add the values to the "DeNeutralize" node.
    """
    value = None
    cdlNeutralNode = nuke.toNode('DeNeutralize')
    # Checks if the node exists
    if not cdlNeutralNode:
        return

    for readNode in NukeHook.queryAllNodes('Read'):
        metadata = readNode.metadata()
        for metadataKey in metadata.keys():
            if fnmatch(metadataKey, 'exr/nuke/*Cdl'):
                value = metadata[metadataKey]
                break

    if not value:
        return

    # The value of the cdl neutral are serialized in a json format
    cdlValues = json.loads(value)
    cdlNeutralNode['slope'].setValue(cdlValues['slope'])
    cdlNeutralNode['offset'].setValue(cdlValues['offset'])
    cdlNeutralNode['power'].setValue(cdlValues['power'])
    cdlNeutralNode['saturation'].setValue(cdlValues['saturation'])

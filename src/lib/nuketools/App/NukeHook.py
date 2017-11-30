from .NukeContext import NukeContext
from basetools.App import Hook
import nuke

class NukeHook(Hook):
    """
    Hook implementation for nuke.
    """

    @classmethod
    def queryAllNodes(cls, nodeType, parent=nuke.Root()):
        """
        Utility method that returns all nodes recursively from a specific type.
        """
        result = nuke.allNodes(nodeType, parent)

        for group in nuke.allNodes("Group", parent):
            result += cls.queryAllNodes(nodeType, group)

        return result


# registering hook
Hook.register(
    'nuke',
    NukeHook,
    NukeContext
)

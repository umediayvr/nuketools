import nuke
import os
import nuketools
from . import DeadlineNukeClient

# shotgun toolkit
try:
    import sgtk
except ImportError:
    shotgunAvailable = False
else:
    shotgunAvailable = True

class SubmitterValidationError(Exception):
    """
    Invalid Write Node Error.
    """

class Submitter(object):
    """
    Utility class to dispatch a render to the farm through deadline.
    """

    @classmethod
    def submit(cls):
        """
        Submit render to the farm.
        """
        # when shotgun is available
        tkWriteNode = None
        if shotgunAvailable:
            eng = sgtk.platform.current_engine()

            # we need to convert any shotgun write node
            # to a regular write node, then when the render dialogue
            # is closed we need to convert back to a shotgun write node
            if "tk-nuke-writenode" in eng.apps:
                tkWriteNode = eng.apps["tk-nuke-writenode"]
                tkWriteNode.convert_to_write_nodes()

        # does not matter what happens at this point we need to be able
        # to recovery the shotgun write nodes (converted previously)
        try:
            writeNodes = cls.writeNodes()
            cls.validateWriteNodes(writeNodes)

        except SubmitterValidationError as error:
            if not nuke.ask('{0}\nDo you want to continue?'.format(error.message)):
                raise error

            # calling deadline render dialogue in case the user wants to go ahead
            # even aware about the issues.
            cls.__deadlineRenderDialogue(writeNodes)

        else:
            # calling deadline render dialogue when everything is fine.
            cls.__deadlineRenderDialogue(writeNodes)

        finally:
            # converting back write nodes to shotgun write nodes
            # (only when shotgun is available)
            if tkWriteNode:
                tkWriteNode.convert_from_write_nodes()

    @classmethod
    def validateWriteNodes(cls, writeNodes, maxWriteNodes=1):
        """
        Validate the list of write nodes.

        The exception "SubmitterValidationError" is raised when
        the validation has failed.
        """
        # making sure just one write node is enabled for rendering, otherwise
        # it should show an error message
        if len(writeNodes) > maxWriteNodes:
            message = 'More than {0} write node:\n{1}'.format(
                maxWriteNodes,
                ', '.join(map(lambda x: x.fullName(), writeNodes))
            )
            raise SubmitterValidationError(message)

        elif len(writeNodes) == 0:
            message = "No write node is enabled for rendering"
            raise SubmitterValidationError(message)

    @classmethod
    def writeNodes(cls):
        """
        Return the write nodes that should be used for rendering on the farm.
        """
        writeNodes = []
        # looking for enabled write nodes
        for writeNode in nuketools.App.NukeHook.queryAllNodes('Write'):
            if not writeNode.knob('disable').value():
                writeNodes.append(writeNode)

        return writeNodes

    @classmethod
    def __deadlineRenderDialogue(cls, writeNodes):
        """
        Display deadline's render dialogue.
        """
        # creating necessary render directories before executing the deadline
        # interface (since the dialogue does not take care of it)
        for writeNode in writeNodes:
            cls.__createRenderDirectory(writeNode)

        # calling deadline render dialogue
        DeadlineNukeClient.main()

    @classmethod
    def __createRenderDirectory(cls, writeNode):
        """
        Create the render directory for a write node.
        """
        renderFilePath = nuke.filename(writeNode)
        if renderFilePath:
            renderFolder = os.path.dirname(renderFilePath)
            if not os.path.exists(renderFolder):
                os.makedirs(renderFolder)

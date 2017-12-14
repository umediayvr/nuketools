import os
import sys
import nuke
from .NukeContext import NukeContext
from basetools.App import Hook

class NukeHook(Hook):
    """
    Hook implementation for nuke.
    """

    def startup(self):
        """
        Perform startup routines.
        """
        super(NukeHook, self).startup()

        if not self.context().hasGUI():
            self.__loadMissingSgtk()

    @classmethod
    def queryAllNodes(cls, nodeType, parent=nuke.Root()):
        """
        Return all nodes from a specific type recursively.
        """
        result = nuke.allNodes(nodeType, parent)

        for group in nuke.allNodes("Group", parent):
            result += cls.queryAllNodes(nodeType, group)

        return result

    @classmethod
    def __loadMissingSgtk(cls):
        """
        Load missing sgtk engine.

        This is necessary to be able to run sgtk on the farm. The reason for that
        is because sgtk modifies the environment variables that were used to
        launch nuke from sgtk desktop. Therefore, context, engine (etc).
        Don't get available on the farm (or anywhere that tries to run nuke
        with those environments). This solution was based on:
        https://github.com/shotgunsoftware/tk-nuke-writenode/wiki/Documentation
        """
        # we need that for the authentication
        if 'TANK_NUKE_ENGINE_INIT_CONTEXT' not in os.environ:
            return

        # initialize tk-nuke engine:
        # Determine the work area path that will be used to
        # create the initial context the engine will be
        # started with.  If a file path was specified on the
        # command line then this will be sys.argv[0]
        workAreaPath = os.environ.get('UMEDIA_ORIGINAL_SCENE_FILE_PATH', '')
        if not workAreaPath and len(sys.argv) > 0 and sys.argv[0].endswith(".nk"):
            # file path was passed through the command line
            workAreaPath = sys.argv[0]

        # don't know the work area
        if not workAreaPath:
            return

        # importing sgtk
        import sgtk

        # the 'deserialize' process is going to set the user in sgtk implicitly,
        # however we want to build a new context from scratch
        if 'TANK_NUKE_ENGINE_INIT_CONTEXT' in os.environ:
            # that is going to take care of the authentication proccess
            ctx = sgtk.Context.deserialize(
                os.environ['TANK_NUKE_ENGINE_INIT_CONTEXT']
            )

        # instantiate an sgtk instance from the current work area path:
        tk = sgtk.sgtk_from_path(workAreaPath)

        # make sure we have synchronised the file system structure from
        # Shotgun (for core v0.15 and above):
        tk.synchronize_filesystem_structure()

        # build a context from the work area path:
        ctx = tk.context_from_path(workAreaPath)

        # Finally, attempt to start the engine for this context:
        sgtk.platform.start_engine("tk-nuke", tk, ctx)


# registering hook
Hook.register(
    'nuke',
    NukeHook,
    NukeContext
)

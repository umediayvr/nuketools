from basetools.App import Context, ContextFileNameError
import nuke

class NukeContext(Context):
    """
    Context implementation for nuke.
    """

    @classmethod
    def fileName(cls):
        """
        Return a string about current file path of the opened file.

        In case the file is not saved, then raise the exception ContextFileNameError.
        """
        if not cls.isEmpty():
            return nuke.root().knob('name').value()

        raise ContextFileNameError(
            "Could not figureout scene name"
        )

    @classmethod
    def isEmpty(cls):
        """
        Return a boolean telling if the scene has never been saved.
        """
        return nuke.root().knob('name').value() == ''

    @classmethod
    def hasModification(cls):
        """
        Return a boolean telling if the scene has modifications.

        This is used to decide if the scene needs to be saved.
        """
        return nuke.modified()

    @classmethod
    def hasGUI(cls):
        """
        Return a boolean telling if application is running with GUI.
        """
        return nuke.GUI

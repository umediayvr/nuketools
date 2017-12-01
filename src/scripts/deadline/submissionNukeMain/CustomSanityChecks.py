import nuke
import DeadlineGlobals

def RunSanityCheck():
	DeadlineGlobals.initSubmitScene = True
	DeadlineGlobals.initLimitGroups = 'nukeRender'
	DeadlineGlobals.initMemoryUsage = 32000
	DeadlineGlobals.initThreads = 8
	DeadlineGlobals.initMachineLimit = 6
	DeadlineGlobals.initGroup = 'farm'
	DeadlineGlobals.initConcurrentTasks = 2
	return True

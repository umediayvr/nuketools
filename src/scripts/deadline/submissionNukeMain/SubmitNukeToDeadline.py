# -- coding: utf-8 --
import os
import sys
import re
import traceback
import subprocess
import ast
import threading
import time
import locale
import errno

try:
    import ConfigParser
except:
    print( "Could not load ConfigParser module, sticky settings will not be loaded/saved" )

try:
    import hiero
    from hiero import core as hcore
except:
    pass

import nuke
import nukescripts

dialog = None
#deadlineCommand = None
dlRenderModes = [ "Use Scene Settings", "Render Full Resolution", "Render using Proxies" ]

class DeadlineDialog( nukescripts.PythonPanel ):
    pools = []
    groups = []

    def __init__( self, maximumPriority, pools, secondaryPools, groups ):

        nukescripts.PythonPanel.__init__( self, "Submit To Deadline", "com.thinkboxsoftware.software.deadlinedialog" )

        width = 620
        height = 748 #Nuke v6 or earlier UI height

        if int(nuke.env[ 'NukeVersionMajor' ]) >= 7: #GPU rendering UI
            height += 20
        if int(nuke.env[ 'NukeVersionMajor' ]) >= 9: #Performance Profiler UI
            height += 40

        self.integrationKVPs = {}

        self.setMinimumSize( width, height ) # width, height
        self.jobTab = nuke.Tab_Knob( "Deadline_JobOptionsTab", "Job Options" )
        self.addKnob( self.jobTab )

        ##########################################################################################
        ## Job Description
        ##########################################################################################

        # Job Name
        self.jobName = nuke.String_Knob( "Deadline_JobName", "Job Name" )
        self.addKnob( self.jobName )
        self.jobName.setTooltip( "The name of your job. This is optional, and if left blank, it will default to 'Untitled'." )
        self.jobName.setValue( "Untitled" )

        # Comment
        self.comment = nuke.String_Knob( "Deadline_Comment", "Comment" )
        self.addKnob( self.comment )
        self.comment.setTooltip( "A simple description of your job. This is optional and can be left blank." )
        self.comment.setValue( "" )

        # Department
        self.department = nuke.String_Knob( "Deadline_Department", "Department" )
        self.addKnob( self.department )
        self.department.setTooltip( "The department you belong to. This is optional and can be left blank." )
        self.department.setValue( "" )

        # Separator
        self.separator1 = nuke.Text_Knob( "Deadline_Separator1", "" )
        self.addKnob( self.separator1 )

        ##########################################################################################
        ## Job Scheduling
        ##########################################################################################

        # Pool
        self.pool = nuke.Enumeration_Knob( "Deadline_Pool", "Pool", pools )
        self.addKnob( self.pool )
        self.pool.setTooltip( "The pool that your job will be submitted to." )
        self.pool.setValue( "none" )

        # Secondary Pool
        self.secondaryPool = nuke.Enumeration_Knob( "Deadline_SecondaryPool", "Secondary Pool", secondaryPools )
        self.addKnob( self.secondaryPool )
        self.secondaryPool.setTooltip( "The secondary pool lets you specify a Pool to use if the primary Pool does not have any available Slaves." )
        self.secondaryPool.setValue( " " )

        # Group
        self.group = nuke.Enumeration_Knob( "Deadline_Group", "Group", groups )
        self.addKnob( self.group )
        self.group.setTooltip( "The group that your job will be submitted to." )
        self.group.setValue( "none" )

        # Priority
        self.priority = nuke.Int_Knob( "Deadline_Priority", "Priority" )
        self.addKnob( self.priority )
        self.priority.setTooltip( "A job can have a numeric priority ranging from 0 to " + str(maximumPriority) + ", where 0 is the lowest priority." )
        self.priority.setValue( 50 )

        # Task Timeout
        self.taskTimeout = nuke.Int_Knob( "Deadline_TaskTimeout", "Task Timeout" )
        self.addKnob( self.taskTimeout )
        self.taskTimeout.setTooltip( "The number of minutes a slave has to render a task for this job before it requeues it. Specify 0 for no limit." )
        self.taskTimeout.setValue( 0 )

        # Auto Task Timeout
        self.autoTaskTimeout = nuke.Boolean_Knob( "Deadline_AutoTaskTimeout", "Enable Auto Task Timeout" )
        self.addKnob( self.autoTaskTimeout )
        self.autoTaskTimeout.setTooltip( "If the Auto Task Timeout is properly configured in the Repository Options, then enabling this will allow a task timeout to be automatically calculated based on the render times of previous frames for the job." )
        self.autoTaskTimeout.setValue( False )

        # Concurrent Tasks
        self.concurrentTasks = nuke.Int_Knob( "Deadline_ConcurrentTasks", "Concurrent Tasks" )
        self.addKnob( self.concurrentTasks )
        self.concurrentTasks.setTooltip( "The number of tasks that can render concurrently on a single slave. This is useful if the rendering application only uses one thread to render and your slaves have multiple CPUs." )
        self.concurrentTasks.setValue( 1 )

        # Limit Concurrent Tasks
        self.limitConcurrentTasks = nuke.Boolean_Knob( "Deadline_LimitConcurrentTasks", "Limit Tasks To Slave's Task Limit" )
        self.addKnob( self.limitConcurrentTasks )
        self.limitConcurrentTasks.setTooltip( "If you limit the tasks to a slave's task limit, then by default, the slave won't dequeue more tasks then it has CPUs. This task limit can be overridden for individual slaves by an administrator." )
        self.limitConcurrentTasks.setValue( False )

        # Machine Limit
        self.machineLimit = nuke.Int_Knob( "Deadline_MachineLimit", "Machine Limit" )
        self.addKnob( self.machineLimit )
        self.machineLimit.setTooltip( "Use the Machine Limit to specify the maximum number of machines that can render your job at one time. Specify 0 for no limit." )
        self.machineLimit.setValue( 0 )

        # Machine List Is Blacklist
        self.isBlacklist = nuke.Boolean_Knob( "Deadline_IsBlacklist", "Machine List Is A Blacklist" )
        self.addKnob( self.isBlacklist )
        self.isBlacklist.setTooltip( "You can force the job to render on specific machines by using a whitelist, or you can avoid specific machines by using a blacklist." )
        self.isBlacklist.setValue( False )

        # Machine List
        self.machineList = nuke.String_Knob( "Deadline_MachineList", "Machine List" )
        self.addKnob( self.machineList )
        self.machineList.setTooltip( "The whitelisted or blacklisted list of machines." )
        self.machineList.setValue( "" )

        self.machineListButton = nuke.PyScript_Knob( "Deadline_MachineListButton", "Browse" )
        self.addKnob( self.machineListButton )

        # Limit Groups
        self.limitGroups = nuke.String_Knob( "Deadline_LimitGroups", "Limits" )
        self.addKnob( self.limitGroups )
        self.limitGroups.setTooltip( "The Limits that your job requires." )
        self.limitGroups.setValue( "" )

        self.limitGroupsButton = nuke.PyScript_Knob( "Deadline_LimitGroupsButton", "Browse" )
        self.addKnob( self.limitGroupsButton )

        # Dependencies
        self.dependencies = nuke.String_Knob( "Deadline_Dependencies", "Dependencies" )
        self.addKnob( self.dependencies )
        self.dependencies.setTooltip( "Specify existing jobs that this job will be dependent on. This job will not start until the specified dependencies finish rendering." )
        self.dependencies.setValue( "" )

        self.dependenciesButton = nuke.PyScript_Knob( "Deadline_DependenciesButton", "Browse" )
        self.addKnob( self.dependenciesButton )

        # On Complete
        self.onComplete = nuke.Enumeration_Knob( "Deadline_OnComplete", "On Job Complete", ("Nothing", "Archive", "Delete") )
        self.addKnob( self.onComplete )
        self.onComplete.setTooltip( "If desired, you can automatically archive or delete the job when it completes." )
        self.onComplete.setValue( "Nothing" )

        # Submit Suspended
        self.submitSuspended = nuke.Boolean_Knob( "Deadline_SubmitSuspended", "Submit Job As Suspended" )
        self.addKnob( self.submitSuspended )
        self.submitSuspended.setTooltip( "If enabled, the job will submit in the suspended state. This is useful if you don't want the job to start rendering right away. Just resume it from the Monitor when you want it to render." )
        self.submitSuspended.setValue( False )

        # Separator
        self.separator1 = nuke.Text_Knob( "Deadline_Separator2", "" )
        self.addKnob( self.separator1 )

        ##########################################################################################
        ## Nuke Options
        ##########################################################################################

        # Frame List
        self.frameListMode = nuke.Enumeration_Knob( "Deadline_FrameListMode", "Frame List", ("Global", "Input", "Custom") )
        self.addKnob( self.frameListMode )
        self.frameListMode.setTooltip( "Select the Global, Input, or Custom frame list mode." )
        self.frameListMode.setValue( "Global" )

        self.frameList = nuke.String_Knob( "Deadline_FrameList", "" )
        self.frameList.clearFlag(nuke.STARTLINE)
        self.addKnob( self.frameList )
        self.frameList.setTooltip( "If Custom frame list mode is selected, this is the list of frames to render." )
        self.frameList.setValue( "" )

        # Chunk Size
        self.chunkSize = nuke.Int_Knob( "Deadline_ChunkSize", "Frames Per Task" )
        self.addKnob( self.chunkSize )
        self.chunkSize.setTooltip( "This is the number of frames that will be rendered at a time for each job task." )
        self.chunkSize.setValue( 10 )

        # NukeX
        self.useNukeX = nuke.Boolean_Knob( "Deadline_UseNukeX", "Render With NukeX" )
        self.addKnob( self.useNukeX )
        self.useNukeX.setTooltip( "If checked, NukeX will be used instead of just Nuke." )
        self.useNukeX.setValue( False )

        # Batch Mode
        self.batchMode = nuke.Boolean_Knob( "Deadline_BatchMode", "Use Batch Mode" )
        self.addKnob( self.batchMode )
        self.batchMode.setTooltip( "This uses the Nuke plugin's Batch Mode. It keeps the Nuke script loaded in memory between frames, which reduces the overhead of rendering the job." )
        self.batchMode.setValue( True )

        # Threads
        self.threads = nuke.Int_Knob( "Deadline_Threads", "Render Threads" )
        self.addKnob( self.threads )
        self.threads.setTooltip( "The number of threads to use for rendering. Set to 0 to have Nuke automatically determine the optimal thread count." )
        self.threads.setValue( 0 )

        # Choose GPU
        self.chooseGpu = nuke.Int_Knob( "Deadline_ChooseGpu", "GPU Override" )
        if int(nuke.env[ 'NukeVersionMajor' ]) >= 8:
            self.addKnob( self.chooseGpu )
        self.chooseGpu.setTooltip( "The GPU to use when rendering." )
        self.chooseGpu.setValue( 0 )
        self.chooseGpu.setEnabled(False)

        # Use GPU
        self.useGpu = nuke.Boolean_Knob( "Deadline_UseGpu", "Use The GPU For Rendering" )
        if int(nuke.env[ 'NukeVersionMajor' ]) >= 7:
            self.addKnob( self.useGpu )
        self.useGpu.setTooltip( "If Nuke should also use the GPU for rendering." )
        self.useGpu.setValue( False )

        # Render Mode
        self.renderMode = nuke.Enumeration_Knob( "Deadline_RenderMode", "Render Mode", dlRenderModes )
        self.addKnob( self.renderMode )
        self.renderMode.setTooltip( "The mode to render with." )
        self.renderMode.setValue( "Use Scene Settings" )

        # Memory Usage
        self.memoryUsage = nuke.Int_Knob( "Deadline_MemoryUsage", "Maximum RAM Usage" )
        self.memoryUsage.setFlag(nuke.STARTLINE)
        self.addKnob( self.memoryUsage )
        self.memoryUsage.setTooltip( "The maximum RAM usage (in MB) to be used for rendering. Set to 0 to not enforce a maximum amount of RAM." )
        self.memoryUsage.setValue( 0 )

        # Enforce Write Node Render Order
        self.enforceRenderOrder = nuke.Boolean_Knob( "Deadline_EnforceRenderOrder", "Enforce Write Node Render Order" )
        self.addKnob( self.enforceRenderOrder )
        self.enforceRenderOrder.setTooltip( "Forces Nuke to obey the render order of Write nodes." )
        self.enforceRenderOrder.setValue( False )

        # Stack Size
        self.stackSize = nuke.Int_Knob( "Deadline_StackSize", "Minimum Stack Size" )
        self.addKnob( self.stackSize )
        self.stackSize.setTooltip( "The minimum stack size (in MB) to be used for rendering. Set to 0 to not enforce a minimum stack size." )
        self.stackSize.setValue( 0 )

        # Continue On Error
        self.continueOnError = nuke.Boolean_Knob( "Deadline_ContinueOnError", "Continue On Error" )
        self.addKnob( self.continueOnError )
        self.continueOnError.setTooltip( "Enable to allow Nuke to continue rendering if it encounters an error." )
        self.continueOnError.setValue( False )

        # Submit Scene
        self.submitScene = nuke.Boolean_Knob( "Deadline_SubmitScene", "Submit Nuke Script File With Job" )
        self.addKnob( self.submitScene )
        self.submitScene.setTooltip( "If this option is enabled, the Nuke script file will be submitted with the job, and then copied locally to the slave machine during rendering." )
        self.submitScene.setValue( False )

        # Performance Profiler
        self.performanceProfiler = nuke.Boolean_Knob( "Deadline_PerformanceProfiler", "Use Performance Profiler" )
        self.performanceProfiler.setFlag(nuke.STARTLINE)
        if int(nuke.env[ 'NukeVersionMajor' ]) >= 9:
            self.addKnob( self.performanceProfiler )
        self.performanceProfiler.setTooltip( "If checked, Nuke will profile the performance of the Nuke script whilst rendering and create a *.xml file per task for later analysis." )
        self.performanceProfiler.setValue( False )

        #Reload Plugin Between Task
        self.reloadPlugin = nuke.Boolean_Knob( "Deadline_ReloadPlugin", "Reload Plugin Between Tasks" )
        self.addKnob( self.reloadPlugin)
        self.reloadPlugin.setTooltip( "If checked, Nuke will force all memory to be released before starting the next task, but this can increase the overhead time between tasks." )
        self.reloadPlugin.setValue( False )

        # Performance Profiler Path
        self.performanceProfilerPath = nuke.File_Knob( "Deadline_PerformanceProfilerDir", "XML Directory" )
        if int(nuke.env[ 'NukeVersionMajor' ]) >= 9:
            self.addKnob( self.performanceProfilerPath )
        self.performanceProfilerPath.setTooltip( "The directory on the network where the performance profile *.xml files will be saved." )
        self.performanceProfilerPath.setValue( "" )
        self.performanceProfilerPath.setEnabled(False)

        # Views
        self.chooseViewsToRender = nuke.Boolean_Knob( "Deadline_ChooseViewsToRender", "Choose Views To Render" )
        self.chooseViewsToRender.setFlag(nuke.STARTLINE)
        self.addKnob( self.chooseViewsToRender)
        self.chooseViewsToRender.setTooltip( "Choose the view(s) you wish to render. This is optional." )

        currentViews = nuke.views()
        self.viewToRenderKnobs = []
        for x, v in enumerate(currentViews):
            currKnob = nuke.Boolean_Knob(('Deadline_ViewToRender_%d' % x), v)
            currKnob.setFlag(0x1000)
            self.viewToRenderKnobs.append((currKnob, v))
            self.addKnob(currKnob)
            currKnob.setValue(True)
            currKnob.setVisible(False) # Hide for now until the checkbox above is enabled.

        # Separator
        self.separator1 = nuke.Text_Knob( "Deadline_Separator3", "" )
        self.addKnob( self.separator1 )

        # Separate Jobs
        self.separateJobs = nuke.Boolean_Knob( "Deadline_SeparateJobs", "Submit Write Nodes As Separate Jobs" )
        self.addKnob( self.separateJobs )
        self.separateJobs.setTooltip( "Enable to submit each write node to Deadline as a separate job." )
        self.separateJobs.setValue( False )

        # Use Node's Frame List
        self.useNodeRange = nuke.Boolean_Knob( "Deadline_UseNodeRange", "Use Node's Frame List" )
        self.addKnob( self.useNodeRange )
        self.useNodeRange.setTooltip( "If submitting each write node as a separate job, enable this to pull the frame range from the write node, instead of using the global frame range." )
        self.useNodeRange.setValue( True )

        #Separate Job Dependencies
        self.separateJobDependencies = nuke.Boolean_Knob( "Deadline_SeparateJobDependencies", "Set Dependencies Based on Write Node Render Order" )
        self.separateJobDependencies.setFlag(nuke.STARTLINE)
        self.addKnob( self.separateJobDependencies )
        self.separateJobDependencies.setTooltip( "Enable each separate job to be dependent on the previous job." )
        self.separateJobDependencies.setValue( False )

        # Separate Tasks
        self.separateTasks = nuke.Boolean_Knob( "Deadline_SeparateTasks", "Submit Write Nodes As Separate Tasks For The Same Job" )
        self.separateTasks.setFlag(nuke.STARTLINE)
        self.addKnob( self.separateTasks )
        self.separateTasks.setTooltip( "Enable to submit a job to Deadline where each task for the job represents a different write node, and all frames for that write node are rendered by its corresponding task." )
        self.separateTasks.setValue( False )

        # Only Submit Selected Nodes
        self.selectedOnly = nuke.Boolean_Knob( "Deadline_SelectedOnly", "Selected Nodes Only" )
        self.selectedOnly.setFlag(nuke.STARTLINE)
        self.addKnob( self.selectedOnly )
        self.selectedOnly.setTooltip( "If enabled, only the selected Write nodes will be rendered." )
        self.selectedOnly.setValue( False )

        # Only Submit Read File Nodes
        self.readFileOnly = nuke.Boolean_Knob( "Deadline_ReadFileOnly", "Nodes With 'Read File' Enabled Only" )
        self.addKnob( self.readFileOnly )
        self.readFileOnly.setTooltip( "If enabled, only the Write nodes that have the 'Read File' option enabled will be rendered." )
        self.readFileOnly.setValue( False )

        # Only Submit Selected Nodes
        self.precompFirst = nuke.Boolean_Knob( "Deadline_PrecompFirst", "Render Precomp Nodes First" )
        self.precompFirst.setFlag(nuke.STARTLINE)
        self.addKnob( self.precompFirst )
        self.precompFirst.setTooltip( "If enabled, all write nodes in precomp nodes will be rendered before the main job." )
        self.precompFirst.setValue( False )

        # Only Submit Read File Nodes
        self.precompOnly = nuke.Boolean_Knob( "Deadline_PrecompOnly", "Only Render Precomp Nodes" )
        self.addKnob( self.precompOnly )
        self.precompOnly.setTooltip( "If enabled, only the Write nodes that are in precomp nodes will be rendered." )
        self.precompOnly.setValue( False )

        # Only Submit Smart Vector Nodes
        self.smartVectorOnly = nuke.Boolean_Knob( "Deadline_SmartVectorOnly", "Only Render Smart Vector Nodes" )
        self.smartVectorOnly.setFlag( nuke.STARTLINE )
        self.addKnob( self.smartVectorOnly )
        self.smartVectorOnly.setTooltip( "If enabled, only the Smart Vector nodes will be rendered." )
        self.smartVectorOnly.setValue( False )

        self.integrationButton = nuke.PyScript_Knob( "Deadline_IntegrationButton", "Pipeline Tools" )
        self.integrationButton.setFlag( nuke.STARTLINE )
        self.addKnob( self.integrationButton )

    def IsMovieFromFormat( self, format ):
        global FormatsDict

        return ( FormatsDict[format][1] == 'movie' )

    def knobChanged( self, knob ):

        if knob == self.useGpu:
            self.chooseGpu.setEnabled( self.useGpu.value() )

        if knob == self.machineListButton:
            GetMachineListFromDeadline()

        if knob == self.limitGroupsButton:
            GetLimitGroupsFromDeadline()

        if knob == self.dependenciesButton:
            GetDependenciesFromDeadline()

        if knob == self.frameList:
            self.frameListMode.setValue( "Custom" )

        if knob == self.frameListMode:
            # In Custom mode, don't change anything
            if self.frameListMode.value() != "Custom":
                startFrame = nuke.Root().firstFrame()
                endFrame = nuke.Root().lastFrame()
                if self.frameListMode.value() == "Input":
                    try:
                        activeInput = nuke.activeViewer().activeInput()
                        startFrame = nuke.activeViewer().node().input(activeInput).frameRange().first()
                        endFrame = nuke.activeViewer().node().input(activeInput).frameRange().last()
                    except:
                        pass

                if startFrame == endFrame:
                    self.frameList.setValue( str(startFrame) )
                else:
                    self.frameList.setValue( str(startFrame) + "-" + str(endFrame) )

        if knob == self.separateJobs or knob == self.separateTasks:
            self.separateJobs.setEnabled( not self.separateTasks.value() )
            self.separateTasks.setEnabled( not self.separateJobs.value() )

            self.separateJobDependencies.setEnabled( self.separateJobs.value() )
            if not self.separateJobs.value():
                self.separateJobDependencies.setValue( self.separateJobs.value() )

            self.useNodeRange.setEnabled( self.separateJobs.value() or self.separateTasks.value() )
            self.precompFirst.setEnabled( ( self.separateJobs.value() or self.separateTasks.value() ) and not self.precompOnly.value() )
            self.precompOnly.setEnabled( ( self.separateJobs.value() or self.separateTasks.value() ) and not self.precompFirst.value() )

            self.smartVectorOnly.setEnabled( ( self.separateJobs.value() or self.separateTasks.value() ) and not self.precompOnly.value()  and not self.precompFirst.value())

            self.frameList.setEnabled( not (self.separateJobs.value() and self.useNodeRange.value()) and not self.separateTasks.value() )
            self.chunkSize.setEnabled( not self.separateTasks.value() )

        if knob == self.precompFirst or knob == self.precompOnly:
            self.precompFirst.setEnabled( not self.precompOnly.value() )
            self.precompOnly.setEnabled( not self.precompFirst.value() )
            self.smartVectorOnly.setEnabled( not (self.precompOnly.value() or self.precompFirst.value()))

        if knob == self.smartVectorOnly:
            self.precompOnly.setEnabled( not self.smartVectorOnly.value() )
            self.precompFirst.setEnabled( not self.smartVectorOnly.value() )

        if knob == self.useNodeRange:
            self.frameListMode.setEnabled( not (self.separateJobs.value() and self.useNodeRange.value()) and not self.separateTasks.value() )
            self.frameList.setEnabled( not (self.separateJobs.value() and self.useNodeRange.value()) and not self.separateTasks.value() )

        if knob == self.performanceProfiler:
            self.performanceProfilerPath.setEnabled( self.performanceProfiler.value() )

        if knob == self.chooseViewsToRender:
            visible = self.chooseViewsToRender.value()
            for vk in self.viewToRenderKnobs:
                vk[0].setVisible(visible)

        if knob == self.integrationButton:
                GetIntegrationInfo()

    def ShowDialog( self ):
        return nukescripts.PythonPanel.showModalDialog( self )

class DeadlineContainerDialog( DeadlineDialog):
    def __init__(self, maximumPriority, pools, secondaryPools, groups, projects, hasComp ):
        super(DeadlineContainerDialog, self).__init__(maximumPriority, pools, secondaryPools, groups)
        self.projects = projects
        self.hasComp = hasComp

        self.studioTab = nuke.Tab_Knob( "Deadline_StudioTab", "Studio Sequence Options" )
        self.addKnob( self.studioTab )

        #If we should submit separate jobs for each comp
        self.submitSequenceJobs = nuke.Boolean_Knob( "Deadline_SubmitSequenceJobs", "Submit Jobs for Comps in Sequence" )
        self.addKnob( self.submitSequenceJobs )
        self.submitSequenceJobs.setValue( False )
        self.submitSequenceJobs.setTooltip("If selected a separate job will be submitted for each comp in the sequence.")

        projectNames = []
        first = ""
        for project in self.projects:
            projectNames.append(str(project.name()))

        #The project
        if len(projectNames) > 0:
            first = str(projectNames[0])
        self.studioProject = nuke.Enumeration_Knob( "Deadline_StudioProject", "Project", projectNames )
        self.addKnob(self.studioProject)
        self.studioProject.setTooltip("The Nuke Studio Project to submit the containers from.")
        self.studioProject.setValue(first)

        #The comps to render
        self.chooseCompsToRender = nuke.Boolean_Knob( "Deadline_ChooseSequencesToRender", "Choose Sequences To Render" )
        self.chooseCompsToRender.setFlag(nuke.STARTLINE)
        self.addKnob( self.chooseCompsToRender)
        self.chooseCompsToRender.setTooltip( "Choose the sequence(s) you wish to render. This is optional." )

        #Get the sequences and their comps
        self.projectSequences = {}
        self.validSequenceNames = []
        self.validComps = {}
        for project in self.projects:
            self.projectSequences[project.name()] = []
            self.validComps[project.name()] = {}
            #This is the current project, grab its sequences
            sequences = project.sequences()
            for sequence in sequences:
                comps = []
                tracks = sequence.binItem().activeItem().items()
                for track in tracks:
                    items = track.items()
                    for item in items:
                        if item.isMediaPresent():
                            infos = item.source().mediaSource().fileinfos()
                            for info in infos:
                                comps.append(info)

                #If there are any comps saved, this is a valid sequence
                self.projectSequences[project.name()].append(sequence.name())
                self.validComps[project.name()][sequence.name()]=comps

        self.sequenceKnobs = []
        for pname in projectNames:
            sequences = self.projectSequences[pname]
            for x, s in enumerate(sequences):
                seqKnob = nuke.Boolean_Knob( ('Deadline_Sequence_%d' % x), s )
                seqKnob.setFlag(nuke.STARTLINE)
                self.sequenceKnobs.append( (seqKnob, (s,pname) ) )
                self.addKnob(seqKnob)
                seqKnob.setValue(True)
                seqKnob.setVisible(False)


    def toggledContainerMode(self):

        self.frameListMode.setEnabled(self.hasComp and (not (self.separateJobs.value() and self.useNodeRange.value()) and not self.separateTasks.value()))
        self.chooseViewsToRender.setEnabled(self.hasComp)
        self.selectedOnly.setEnabled(self.hasComp)
        self.frameList.setEnabled(self.hasComp and (not (self.separateJobs.value() and self.useNodeRange.value()) and not self.separateTasks.value()))
        self.chunkSize.setEnabled(self.hasComp and not self.separateTasks.value())
        self.separateJobs.setEnabled( self.hasComp and not self.separateTasks.value() )
        self.separateTasks.setEnabled( self.hasComp and not self.separateJobs.value() )

        if self.submitSequenceJobs.value():
            self.studioProject.setEnabled(True)
            self.chooseCompsToRender.setEnabled(True)
            for sk in self.sequenceKnobs:
                sk[0].setEnabled(True)
        else:
            self.studioProject.setEnabled(False)
            self.chooseCompsToRender.setEnabled(False)
            for sk in self.sequenceKnobs:
                sk[0].setEnabled(False)


    def knobChanged(self, knob):
        super(DeadlineContainerDialog, self).knobChanged(knob)

        if knob == self.submitSequenceJobs:
            self.toggledContainerMode()

        if knob == self.chooseCompsToRender:
            self.populateSequences()

        if knob == self.studioProject:
            self.populateSequences()

    def populateSequences(self):
        visible = self.chooseCompsToRender.value()
        projectName = self.studioProject.value()

        for sk in self.sequenceKnobs:
            if sk[1][1] == projectName:
                sk[0].setVisible(visible)
            else:
                sk[0].setVisible(False)

    def ShowDialog( self ):
        self.toggledContainerMode()
        return nukescripts.PythonPanel.showModalDialog( self )

def GetDeadlineCommand():
    deadlineBin = ""
    try:
        deadlineBin = os.environ['DEADLINE_PATH']
    except KeyError:
        #if the error is a key error it means that DEADLINE_PATH is not set. however Deadline command may be in the PATH or on OSX it could be in the file /Users/Shared/Thinkbox/DEADLINE_PATH
        pass

    # On OSX, we look for the DEADLINE_PATH file if the environment variable does not exist.
    if deadlineBin == "" and  os.path.exists( "/Users/Shared/Thinkbox/DEADLINE_PATH" ):
        with open( "/Users/Shared/Thinkbox/DEADLINE_PATH" ) as f:
            deadlineBin = f.read().strip()

    deadlineCommand = os.path.join(deadlineBin, "deadlinecommand")

    return deadlineCommand

def CallDeadlineCommand( arguments, hideWindow=True ):
    deadlineCommand = GetDeadlineCommand()

    startupinfo = None
    if hideWindow and os.name == 'nt':
        # Python 2.6 has subprocess.STARTF_USESHOWWINDOW, and Python 2.7 has subprocess._subprocess.STARTF_USESHOWWINDOW, so check for both.
        if hasattr( subprocess, '_subprocess' ) and hasattr( subprocess._subprocess, 'STARTF_USESHOWWINDOW' ):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
        elif hasattr( subprocess, 'STARTF_USESHOWWINDOW' ):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    environment = {}
    for key in os.environ.keys():
        environment[key] = str(os.environ[key])

    # Need to set the PATH, cuz windows seems to load DLLs from the PATH earlier that cwd....
    if os.name == 'nt':
        deadlineCommandDir = os.path.dirname( deadlineCommand )
        if not deadlineCommandDir == "" :
            environment['PATH'] = deadlineCommandDir + os.pathsep + os.environ['PATH']

    arguments.insert( 0, deadlineCommand)
    output = ""

    # Specifying PIPE for all handles to workaround a Python bug on Windows. The unused handles are then closed immediatley afterwards.
    proc = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo, env=environment)
    output, errors = proc.communicate()

    return output

def GetIntegrationInfo():
    global dialog

    integrationPath = GetRepositoryPath("submission/Integration/Main")
    integrationScript = integrationPath + "/IntegrationUIStandAlone.py"
    additionalArgs = [ "Draft", "Shotgun", "FTrack", "NIM", "0" ]

    tempKVPs = GetProjMgmtInfo( integrationScript, additionalArgs )

    if len( tempKVPs ) > 0:
        dialog.integrationKVPs = tempKVPs

def GetProjMgmtInfo( scriptPath, additionalArgs=[] ):
    argArray = ["ExecuteScript", scriptPath, "Nuke"]
    for arg in additionalArgs:
        argArray.append(arg)

    output = CallDeadlineCommand( argArray, False )
    outputLines = output.splitlines()

    keyValuePairs = {}

    for line in outputLines:
        line = line.strip()
        if not line.startswith("("):
            tokens = line.split( '=', 1 )

            if len( tokens ) > 1:
                key = tokens[0]
                value = tokens[1]

                keyValuePairs[key] = value

    return keyValuePairs

def GetMachineListFromDeadline():
    global dialog
    output = CallDeadlineCommand( ["-selectmachinelist", dialog.machineList.value()], False )
    output = output.replace( "\r", "" ).replace( "\n", "" )
    if output != "Action was cancelled by user":
        dialog.machineList.setValue( output )


def GetLimitGroupsFromDeadline():
    global dialog
    output = CallDeadlineCommand( ["-selectlimitgroups", dialog.limitGroups.value()], False )
    output = output.replace( "\r", "" ).replace( "\n", "" )
    if output != "Action was cancelled by user":
        dialog.limitGroups.setValue( output )

def GetDependenciesFromDeadline():
    global dialog
    output = CallDeadlineCommand( ["-selectdependencies", dialog.dependencies.value()], False )
    output = output.replace( "\r", "" ).replace( "\n", "" )
    if output != "Action was cancelled by user":
        dialog.dependencies.setValue( output )

# Checks a path to make sure it has an extension
def HasExtension( path ):
    filename = os.path.basename( path )

    return filename.rfind( "." ) > -1

# Checks if path is local (c, d, or e drive).
def IsPathLocal( path ):
    lowerPath = path.lower()
    if lowerPath.startswith( "c:" ) or lowerPath.startswith( "d:" ) or lowerPath.startswith( "e:" ):
        return True
    return False

# Checks if the given filename ends with a movie extension
def IsMovie( path ):
    lowerPath = path.lower()
    if lowerPath.endswith( ".mov" ):
        return True
    return False

# Checks if the filename is padded (ie: \\output\path\filename_%04.tga).
def IsPadded( path ):
    #Check for padding in the file
    paddingRe = re.compile( "%([0-9]+)d", re.IGNORECASE )
    if paddingRe.search( path ) != None:
        return True
    elif path.find( "#" ) > -1:
        return True
    return False

def RightReplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)

def StrToBool(str):
    return str.lower() in ("yes", "true", "t", "1", "on")

# Parses through the filename looking for the last padded pattern, replaces
# it with the correct number of #'s, and returns the new padded filename.
def GetPaddedPath( path ):
    # paddingRe = re.compile( "%([0-9]+)d", re.IGNORECASE )

    # paddingMatch = paddingRe.search( path )
    # if paddingMatch != None:
        # paddingSize = int(paddingMatch.lastgroup)

        # padding = ""
        # while len(padding) < paddingSize:
            # padding = padding + "#"

        # path = paddingRe.sub( padding, path, 1 )

    paddingRe = re.compile( "([0-9]+)", re.IGNORECASE )

    paddingMatches = paddingRe.findall( path )
    if paddingMatches != None and len( paddingMatches ) > 0:
        paddingString = paddingMatches[ len( paddingMatches ) - 1 ]
        paddingSize = len(paddingString)

        padding = ""
        while len(padding) < paddingSize:
            padding = padding + "#"

        path = RightReplace( path, paddingString, padding, 1 )

    return path

def buildKnob(name, abr):
    try:
        root = nuke.Root()
        if "Deadline" not in root.knobs():
            tabKnob = nuke.Tab_Knob("Deadline")
            root.addKnob(tabKnob)

        if name in root.knobs():
            return root.knob( name )
        else:
            tKnob = nuke.String_Knob( name, abr )
            root.addKnob ( tKnob )
            return  tKnob
    except:
        print "Error in knob creation. "+ name + " " + abr

def WriteStickySettings( dialog, configFile ):

    try:
        print "Writing sticky settings..."
        config = ConfigParser.ConfigParser()
        config.add_section( "Sticky" )

        config.set( "Sticky", "FrameListMode", dialog.frameListMode.value() )
        config.set( "Sticky", "CustomFrameList", dialog.frameList.value().strip() )

        config.set( "Sticky", "Department", dialog.department.value() )
        config.set( "Sticky", "Pool", dialog.pool.value() )
        config.set( "Sticky", "SecondaryPool", dialog.secondaryPool.value() )
        config.set( "Sticky", "Group", dialog.group.value() )
        config.set( "Sticky", "Priority", str( dialog.priority.value() ) )
        config.set( "Sticky", "MachineLimit", str( dialog.machineLimit.value() ) )
        config.set( "Sticky", "IsBlacklist", str( dialog.isBlacklist.value() ) )
        config.set( "Sticky", "MachineList", dialog.machineList.value() )
        config.set( "Sticky", "LimitGroups", dialog.limitGroups.value() )
        config.set( "Sticky", "SubmitSuspended", str( dialog.submitSuspended.value() ) )
        config.set( "Sticky", "ChunkSize", str( dialog.chunkSize.value() ) )
        config.set( "Sticky", "ConcurrentTasks", str( dialog.concurrentTasks.value() ) )
        config.set( "Sticky", "LimitConcurrentTasks", str( dialog.limitConcurrentTasks.value() ) )
        config.set( "Sticky", "Threads", str( dialog.threads.value() ) )
        config.set( "Sticky", "SubmitScene", str( dialog.submitScene.value() ) )
        config.set( "Sticky", "BatchMode", str( dialog.batchMode.value() ) )
        config.set( "Sticky", "ContinueOnError", str( dialog.continueOnError.value() ) )
        config.set( "Sticky", "UseNodeRange", str( dialog.useNodeRange.value() ) )
        config.set( "Sticky", "UseGpu", str( dialog.useGpu.value() ) )
        config.set( "Sticky", "ChooseGpu", str( dialog.chooseGpu.value() ) )
        config.set( "Sticky", "EnforceRenderOrder", str( dialog.enforceRenderOrder.value() ) )
        config.set( "Sticky", "RenderMode", str(dialog.renderMode.value() ) )
        config.set( "Sticky", "PerformanceProfiler", str(dialog.performanceProfiler.value() ) )
        config.set( "Sticky", "ReloadPlugin", str( dialog.reloadPlugin.value() ) )
        config.set( "Sticky", "PerformanceProfilerPath", dialog.performanceProfilerPath.value() )

        fileHandle = open( unicode( configFile, "utf-8" ), "w" )
        config.write( fileHandle )
        fileHandle.close()
    except:
        print( "Could not write sticky settings" )
        print traceback.format_exc()

    try:
        #Saves all the sticky setting to the root
        tKnob = buildKnob( "FrameListMode" , "frameListMode")
        tKnob.setValue( dialog.frameListMode.value() )

        tKnob = buildKnob( "CustomFrameList", "customFrameList" )
        tKnob.setValue( dialog.frameList.value().strip() )

        tKnob = buildKnob( "Department", "department" )
        tKnob.setValue( dialog.department.value() )

        tKnob = buildKnob( "Pool", "pool" )
        tKnob.setValue( dialog.pool.value() )

        tKnob = buildKnob( "SecondaryPool", "secondaryPool" )
        tKnob.setValue( dialog.secondaryPool.value() )

        tKnob = buildKnob( "Group", "group" )
        tKnob.setValue( dialog.group.value() )

        tKnob = buildKnob( "Priority", "priority" )
        tKnob.setValue( str( dialog.priority.value() ) )

        tKnob = buildKnob( "MachineLimit", "machineLimit" )
        tKnob.setValue( str( dialog.machineLimit.value() ) )

        tKnob = buildKnob( "IsBlacklist", "isBlacklist" )
        tKnob.setValue( str( dialog.isBlacklist.value() ) )

        tKnob = buildKnob( "MachineList", "machineList" )
        tKnob.setValue( dialog.machineList.value() )

        tKnob = buildKnob( "LimitGroups", "limitGroups" )
        tKnob.setValue( dialog.limitGroups.value() )

        tKnob = buildKnob( "SubmitSuspended", "submitSuspended" )
        tKnob.setValue( str( dialog.submitSuspended.value() ) )

        tKnob = buildKnob( "ChunkSize", "chunkSize" )
        tKnob.setValue( str( dialog.chunkSize.value() ) )

        tKnob = buildKnob( "ConcurrentTasks", "concurrentTasks" )
        tKnob.setValue( str( dialog.concurrentTasks.value() ) )

        tKnob = buildKnob( "LimitConcurrentTasks", "limitConcurrentTasks" )
        tKnob.setValue( str( dialog.limitConcurrentTasks.value() ) )

        tKnob = buildKnob( "Threads", "threads" )
        tKnob.setValue( str( dialog.threads.value() ) )

        tKnob = buildKnob( "SubmitScene", "submitScene" )
        tKnob.setValue( str( dialog.submitScene.value() ) )

        tKnob = buildKnob( "BatchMode", "batchMode" )
        tKnob.setValue( str( dialog.batchMode.value() ) )

        tKnob = buildKnob( "ContinueOnError", "continueOnError" )
        tKnob.setValue( str( dialog.continueOnError.value() ) )

        tKnob = buildKnob( "UseNodeRange", "useNodeRange" )
        tKnob.setValue( str( dialog.useNodeRange.value() ) )

        tKnob = buildKnob( "UseGpu", "useGpu" )
        tKnob.setValue( str( dialog.useGpu.value() ) )

        tKnob = buildKnob( "ChooseGpu", "chooseGpu" )
        tKnob.setValue( str( dialog.chooseGpu.value() ) )

        tKnob = buildKnob( "EnforceRenderOrder", "enforceRenderOrder" )
        tKnob.setValue( str( dialog.enforceRenderOrder.value() ) )

        tKnob = buildKnob( "DeadlineRenderMode", "deadlineRenderMode" )
        tKnob.setValue( str( dialog.renderMode.value() ) )

        tKnob = buildKnob( "PerformanceProfiler", "performanceProfiler" )
        tKnob.setValue( str( dialog.performanceProfiler.value() ) )

        tKnob = buildKnob( "ReloadPlugin", "reloadPlugin" )
        tKnob.setValue( str( dialog.reloadPlugin.value() ) )

        tKnob = buildKnob( "PerformanceProfilerPath", "performanceProfilerPath" )
        tKnob.setValue( dialog.performanceProfilerPath.value() )

        # If the Nuke script has been modified, then save it to preserve SG settings.
        root = nuke.Root()
        if root.modified():
            if root.name() != "Root":
                nuke.scriptSave( root.name() )

    except:
        print( "Could not write knob settings." )
        print traceback.format_exc()

def SubmitSequenceJobs(dialog, deadlineTemp, tempDependencies, semaphore, extraInfo):
    global ResolutionsDict
    global FormatsDict
    projectName = dialog.studioProject.value()
    #Get the comps that will be submitted for the project selected in the dialog
    comps = dialog.validComps[projectName]

    node = None

    #Get the sequences that will be submitted
    sequenceKnobs = dialog.sequenceKnobs
    allSequences = not dialog.chooseCompsToRender.value()

    sequences = []
    for knobTuple in sequenceKnobs:
        if knobTuple[1][1] == projectName:
            if not allSequences:
                if knobTuple[0].value():
                    sequences.append(knobTuple[1][0])
            else:
                sequences.append(knobTuple[1][0])

    allComps = []
    for sequence in sequences:
        for comp in comps[sequence]:
            allComps.append(comp)

    batchName = str(str(dialog.jobName.value())+" ("+projectName + ")")

    jobCount = len(allComps)
    currentJobIndex = 1

    previousJobId = ""
    #Submit all comps in each sequence
    for sequence in sequences:
        compNum = 1
        for comp in comps[sequence]:
            print "Preparing job #%d for submission.." % currentJobIndex

            progressTask = nuke.ProgressTask("Job Submission")
            progressTask.setMessage("Creating Job Info File")
            progressTask.setProgress(0)
            if len(comps[sequence]) > 1:
                name = sequence + " - Comp "+str(compNum)
            else:
                name = sequence

            if dialog.separateJobDependencies.value():
                if len(previousJobId) > 1 and jobCount > 1 and not tempDependencies == "":
                    tempDependencies = tempDependencies + "," + previousJobId
                elif tempDependencies == "":
                    tempDependencies = previousJobId

            # Create the submission info file (append job count since we're submitting multiple jobs at the same time in different threads)
            jobInfoFile = unicode(deadlineTemp, "utf-8") + (u"/nuke_submit_info%d.job" % currentJobIndex)
            fileHandle = open( jobInfoFile, "w" )
            fileHandle.write( "Plugin=Nuke\n" )
            fileHandle.write( "Name=%s\n" % str(str(dialog.jobName.value())+"("+name+")") )
            fileHandle.write( "Comment=%s\n" % dialog.comment.value() )
            fileHandle.write( "Department=%s\n" % dialog.department.value() )
            fileHandle.write( "Pool=%s\n" % dialog.pool.value() )
            if dialog.secondaryPool.value() == "":
                fileHandle.write( "SecondaryPool=\n" )
            else:
                fileHandle.write( "SecondaryPool=%s\n" % dialog.secondaryPool.value() )
            fileHandle.write( "Group=%s\n" % dialog.group.value() )
            fileHandle.write( "Priority=%s\n" % dialog.priority.value() )
            fileHandle.write( "MachineLimit=%s\n" % dialog.machineLimit.value() )
            fileHandle.write( "TaskTimeoutMinutes=%s\n" % dialog.taskTimeout.value() )
            fileHandle.write( "EnableAutoTimeout=%s\n" % dialog.autoTaskTimeout.value() )
            fileHandle.write( "ConcurrentTasks=%s\n" % dialog.concurrentTasks.value() )
            fileHandle.write( "LimitConcurrentTasksToNumberOfCpus=%s\n" % dialog.limitConcurrentTasks.value() )
            fileHandle.write( "LimitGroups=%s\n" % dialog.limitGroups.value() )
            fileHandle.write( "JobDependencies=%s\n" %  tempDependencies)
            fileHandle.write( "OnJobComplete=%s\n" % dialog.onComplete.value() )

            tempFrameList = str(int(comp.startFrame())) + "-" + str(int(comp.endFrame()))

            fileHandle.write( "Frames=%s\n" % tempFrameList )
            fileHandle.write( "ChunkSize=1\n" )

            if dialog.submitSuspended.value():
                fileHandle.write( "InitialStatus=Suspended\n" )

            if dialog.isBlacklist.value():
                fileHandle.write( "Blacklist=%s\n" % dialog.machineList.value() )
            else:
                fileHandle.write( "Whitelist=%s\n" % dialog.machineList.value() )

            #NOTE: We're not writing out NIM/FTrack/Shotgun or Draft extra info here because we do not have a defined output file to operate on in this case.

            if jobCount > 1:
                fileHandle.write( "BatchName=%s\n" % batchName )

            fileHandle.close()

            # Update task progress
            progressTask.setMessage("Creating Plugin Info File")
            progressTask.setProgress(10)

            # Create the plugin info file
            pluginInfoFile = unicode( deadlineTemp, "utf-8" ) + (u"/nuke_plugin_info%d.job" % currentJobIndex)
            fileHandle = open( pluginInfoFile, "w" )
            fileHandle.write( "SceneFile=%s\n" % comp.filename() )
            fileHandle.write( "Version=%s.%s\n" % (nuke.env[ 'NukeVersionMajor' ], nuke.env['NukeVersionMinor']) )
            fileHandle.write( "Threads=%s\n" % dialog.threads.value() )
            fileHandle.write( "RamUse=%s\n" % dialog.memoryUsage.value() )
            fileHandle.write( "BatchMode=%s\n" % dialog.batchMode.value())
            fileHandle.write( "BatchModeIsMovie=%s\n" % False )

            fileHandle.write( "NukeX=%s\n" % dialog.useNukeX.value() )

            if int(nuke.env[ 'NukeVersionMajor' ]) >= 7:
                fileHandle.write( "UseGpu=%s\n" % dialog.useGpu.value() )

            if int(nuke.env[ 'NukeVersionMajor' ]) >= 8:
                fileHandle.write( "GpuOverride=%s\n" % dialog.chooseGpu.value() )

            fileHandle.write( "RenderMode=%s\n" % dialog.renderMode.value() )
            fileHandle.write( "EnforceRenderOrder=%s\n" % dialog.enforceRenderOrder.value() )
            fileHandle.write( "ContinueOnError=%s\n" % dialog.continueOnError.value() )

            if int(nuke.env[ 'NukeVersionMajor' ]) >= 9:
                fileHandle.write( "PerformanceProfiler=%s\n" % dialog.performanceProfiler.value() )
                fileHandle.write( "PerformanceProfilerDir=%s\n" % dialog.performanceProfilerPath.value() )

            fileHandle.write( "StackSize=%s\n" % dialog.stackSize.value() )
            fileHandle.close()

            # Update task progress
            progressTask.setMessage("Submitting Job %d to Deadline" % currentJobIndex)
            progressTask.setProgress(30)

            # Submit the job to Deadline
            args = []
            args.append( jobInfoFile.encode(locale.getpreferredencoding() ) )
            args.append( pluginInfoFile.encode(locale.getpreferredencoding() ) )
            args.append( comp.filename() )

            tempResults = ""

            # Submit Job
            progressTask.setProgress(50)

            # If submitting multiple jobs, acquire the semaphore so that only one job is submitted at a time.
            if semaphore:
                semaphore.acquire()

            try:
                tempResults = CallDeadlineCommand( args )
            finally:
                # Release the semaphore if necessary.
                if semaphore:
                    semaphore.release()

            # Update task progress
            progressTask.setMessage("Complete!")
            progressTask.setProgress(100)

            print "Job submission #%d complete" % currentJobIndex

            # If submitting multiple jobs, just print the results to the console, otherwise show them to the user.
            if semaphore:
                print tempResults
            else:
                nuke.executeInMainThread( nuke.message, tempResults )

            currentJobIndex = currentJobIndex + 1
            compNum = compNum + 1

            for line in tempResults.splitlines():
                if line.startswith("JobID="):
                    previousJobId = line[6:]
                    break

    nuke.executeInMainThread( nuke.message, "Sequence Job Submission complete. "+str(jobCount)+" Job(s) submitted to Deadline." )

def EncodeAsUTF16String( unicodeString ):
    return unicodeString.decode( "utf-8" ).encode( "utf-16-le" )

def SubmitJob( dialog, root, node, writeNodes, deadlineTemp, tempJobName, tempFrameList, tempDependencies, tempChunkSize, tempIsMovie, jobCount, semaphore,  extraInfo ):
    global ResolutionsDict
    global FormatsDict

    viewsToRender = []
    if dialog.chooseViewsToRender.value():
        for vk in dialog.viewToRenderKnobs:
            if vk[0].value():
                viewsToRender.append(vk[1])
    else:
        viewsToRender = nuke.views()


    print "Preparing job #%d for submission.." % jobCount

    # Create a task in Nuke's progress  bar dialog
    #progressTask = nuke.ProgressTask("Submitting %s to Deadline" % tempJobName)
    progressTask = nuke.ProgressTask("Job Submission")
    progressTask.setMessage("Creating Job Info File")
    progressTask.setProgress(0)

    batchName = dialog.jobName.value()
    # Create the submission info file (append job count since we're submitting multiple jobs at the same time in different threads)
    jobInfoFile = unicode(deadlineTemp, "utf-8") + (u"/nuke_submit_info%d.job" % jobCount)
    fileHandle = open( jobInfoFile, "wb" )
    fileHandle.write( EncodeAsUTF16String( "Plugin=Nuke\n" ) )
    fileHandle.write( EncodeAsUTF16String( "Name=%s\n" % tempJobName ) )
    fileHandle.write( EncodeAsUTF16String( "Comment=%s\n" % dialog.comment.value() ) )
    fileHandle.write( EncodeAsUTF16String( "Department=%s\n" % dialog.department.value() ) )
    fileHandle.write( EncodeAsUTF16String( "Pool=%s\n" % dialog.pool.value() ) )
    if dialog.secondaryPool.value() == "":
        fileHandle.write( EncodeAsUTF16String( "SecondaryPool=\n" ) )
    else:
        fileHandle.write( EncodeAsUTF16String( "SecondaryPool=%s\n" % dialog.secondaryPool.value() ) )
    fileHandle.write( EncodeAsUTF16String( "Group=%s\n" % dialog.group.value() ) )
    fileHandle.write( EncodeAsUTF16String( "Priority=%s\n" % dialog.priority.value() ) )
    fileHandle.write( EncodeAsUTF16String( "MachineLimit=%s\n" % dialog.machineLimit.value() ) )
    fileHandle.write( EncodeAsUTF16String( "TaskTimeoutMinutes=%s\n" % dialog.taskTimeout.value() ) )
    fileHandle.write( EncodeAsUTF16String( "EnableAutoTimeout=%s\n" % dialog.autoTaskTimeout.value() ) )
    fileHandle.write( EncodeAsUTF16String( "ConcurrentTasks=%s\n" % dialog.concurrentTasks.value() ) )
    fileHandle.write( EncodeAsUTF16String( "LimitConcurrentTasksToNumberOfCpus=%s\n" % dialog.limitConcurrentTasks.value() ) )
    fileHandle.write( EncodeAsUTF16String( "LimitGroups=%s\n" % dialog.limitGroups.value() ) )
    fileHandle.write( EncodeAsUTF16String( "JobDependencies=%s\n" %  tempDependencies ) )
    fileHandle.write( EncodeAsUTF16String( "OnJobComplete=%s\n" % dialog.onComplete.value() ) )
    fileHandle.write( EncodeAsUTF16String( "ForceReloadPlugin=%s\n" % dialog.reloadPlugin.value() ) )

    if dialog.separateTasks.value():
        writeNodeCount = 0
        for tempNode in writeNodes:
            if not tempNode.knob( 'disable' ).value():
                enterLoop = True
                if dialog.readFileOnly.value() and tempNode.knob( 'reading' ):
                    enterLoop = enterLoop and tempNode.knob( 'reading' ).value()
                if dialog.selectedOnly.value():
                    enterLoop = enterLoop and IsNodeOrParentNodeSelected(tempNode)

                if enterLoop:
                    writeNodeCount += 1


        fileHandle.write( EncodeAsUTF16String( "Frames=0-%s\n" % (writeNodeCount-1) ) )
        fileHandle.write( EncodeAsUTF16String( "ChunkSize=1\n" ) )
    else:
        fileHandle.write( EncodeAsUTF16String( "Frames=%s\n" % tempFrameList ) )
        fileHandle.write( EncodeAsUTF16String( "ChunkSize=%s\n" % tempChunkSize ) )

    if dialog.submitSuspended.value():
        fileHandle.write( EncodeAsUTF16String( "InitialStatus=Suspended\n" ) )

    if dialog.isBlacklist.value():
        fileHandle.write( EncodeAsUTF16String( "Blacklist=%s\n" % dialog.machineList.value() ) )
    else:
        fileHandle.write( EncodeAsUTF16String( "Whitelist=%s\n" % dialog.machineList.value() ) )

    extraKVPIndex = 0

    index = 0

    for v in viewsToRender:
        if dialog.separateJobs.value():

            #gets the filename/proxy filename and evaluates TCL + vars, but *doesn't* swap frame padding
            fileValue = nuke.filename( node )

            if ( root.proxy() and node.knob( 'proxy' ).value() != "" ):
                evaluatedValue = node.knob( 'proxy' ).evaluate(view=v)
            else:
                evaluatedValue = node.knob( 'file' ).evaluate(view=v)

            if fileValue != None and fileValue != "" and evaluatedValue != None and evaluatedValue != "":
                tempPath, tempFilename = os.path.split( evaluatedValue )
                if IsPadded( os.path.basename( fileValue ) ):
                    tempFilename = GetPaddedPath( tempFilename )

                paddedPath = os.path.join( tempPath, tempFilename )
                #Handle cases where file name might start with an escape character
                paddedPath = paddedPath.replace( "\\", "/" )

                fileHandle.write( EncodeAsUTF16String( "OutputFilename%i=%s\n" % ( index, paddedPath ) ) )

                #Check if the Write Node will be modifying the output's Frame numbers
                if node.knob( 'frame_mode' ):
                    if ( node.knob( 'frame_mode' ).value() == "offset" ):
                        fileHandle.write( EncodeAsUTF16String( "ExtraInfoKeyValue%d=OutputFrameOffset%i=%s\n" % ( extraKVPIndex,index, str( int( node.knob( 'frame' ).value() ) ) ) ) )
                        extraKVPIndex += 1
                    elif ( node.knob( 'frame_mode' ).value() == "start at" or node.knob( 'frame_mode' ).value() == "start_at"):
                        franges = nuke.FrameRanges( tempFrameList )
                        fileHandle.write( EncodeAsUTF16String( "ExtraInfoKeyValue%d=OutputFrameOffset%i=%s\n" % ( extraKVPIndex,index, str( int( node.knob( 'frame' ).value() ) - franges.minFrame() ) ) ) )
                        extraKVPIndex += 1
                    else:
                        #TODO: Handle 'expression'? Would be much harder
                        pass
                index+=1
        else:
            for tempNode in writeNodes:
                if not tempNode.knob( 'disable' ).value():
                    enterLoop = True
                    if tempNode.Class() != "SmartVector" and dialog.readFileOnly.value() and tempNode.knob( 'reading' ):
                        enterLoop = enterLoop and tempNode.knob( 'reading' ).value()
                    if dialog.selectedOnly.value():
                        enterLoop = enterLoop and IsNodeOrParentNodeSelected(tempNode)

                    if enterLoop:
                        #gets the filename/proxy filename and evaluates TCL + vars, but *doesn't* swap frame padding
                        fileValue = nuke.filename( tempNode )
                        if ( root.proxy() and tempNode.knob( 'proxy' ).value() != "" ):
                            evaluatedValue = tempNode.knob( 'proxy' ).evaluate(view=v)
                        else:
                            evaluatedValue = tempNode.knob( 'file' ).evaluate(view=v)

                        if fileValue != None and fileValue != "" and evaluatedValue != None and evaluatedValue != "":
                            tempPath, tempFilename = os.path.split( evaluatedValue )

                            if dialog.separateTasks.value():
                                fileHandle.write( EncodeAsUTF16String( "OutputDirectory%s=%s\n" % ( index, tempPath ) ) )
                            else:
                                if IsPadded( os.path.basename( fileValue ) ):
                                    tempFilename = GetPaddedPath( tempFilename )

                                paddedPath = os.path.join( tempPath, tempFilename )
                                #Handle escape character cases
                                paddedPath = paddedPath.replace( "\\", "/" )

                                fileHandle.write( EncodeAsUTF16String( "OutputFilename%s=%s\n" % (index, paddedPath ) ) )

                                #Check if the Write Node will be modifying the output's Frame numbers
                                if tempNode.knob( 'frame_mode' ):
                                    frameVal = tempNode.knob( 'frame' ).value()
                                    if frameVal != "":
                                        if ( tempNode.knob( 'frame_mode' ).value() == "offset" ):
                                            fileHandle.write( EncodeAsUTF16String( "ExtraInfoKeyValue%d=OutputFrameOffset%s=%s\n" % ( extraKVPIndex, index, str( int( frameVal ) ) ) ) )
                                            extraKVPIndex += 1
                                        elif ( tempNode.knob( 'frame_mode' ).value() == "start at" or tempNode.knob( 'frame_mode' ).value() == "start_at"):
                                            franges = nuke.FrameRanges( tempFrameList )
                                            fileHandle.write( EncodeAsUTF16String( "ExtraInfoKeyValue%d=OutputFrameOffset%s=%s\n" % ( extraKVPIndex, index, str( int( frameVal ) - franges.minFrame() ) ) ) )
                                            extraKVPIndex += 1
                                        else:
                                            #TODO: Handle 'expression'? Would be much harder
                                            pass

                            index = index + 1

    # Write the shotgun data.
    groupBatch = False


    if 'integrationSettingsPath' in dialog.integrationKVPs:
        with open( dialog.integrationKVPs['integrationSettingsPath'] ) as file:
            for line in file.readlines():
                fileHandle.write( EncodeAsUTF16String(line) )

        if 'extraKVPIndex' in dialog.integrationKVPs:
            extraKVPIndex = int( dialog.integrationKVPs[ 'extraKVPIndex' ] )

        if 'batchMode' in dialog.integrationKVPs:
            if dialog.integrationKVPs[ 'batchMode' ] == "True":
                groupBatch = True

        for i in range (6, 10):
            fileHandle.write( EncodeAsUTF16String( "ExtraInfo%d=%s\n" % ( i, extraInfo[ i ] ) ) )
    else:
        for i in range (0, 10):
            fileHandle.write( EncodeAsUTF16String( "ExtraInfo%d=%s\n" % ( i, extraInfo[ i ] ) ) )

    if groupBatch or dialog.separateJobs.value():
        fileHandle.write( EncodeAsUTF16String( "BatchName=%s\n" % batchName ) )

    fileHandle.close()

    # Update task progress
    progressTask.setMessage("Creating Plugin Info File")
    progressTask.setProgress(10)

    # Create the plugin info file
    pluginInfoFile = unicode(deadlineTemp, "utf-8") + (u"/nuke_plugin_info%d.job" % jobCount)
    fileHandle = open( pluginInfoFile, "w" )
    if not dialog.submitScene.value():
        fileHandle.write( EncodeAsUTF16String( "SceneFile=%s\n" % root.name() ) )

    fileHandle.write( EncodeAsUTF16String( "Version=%s.%s\n" % (nuke.env[ 'NukeVersionMajor' ], nuke.env['NukeVersionMinor']) ) )
    fileHandle.write( EncodeAsUTF16String( "Threads=%s\n" % dialog.threads.value() ) )
    fileHandle.write( EncodeAsUTF16String( "RamUse=%s\n" % dialog.memoryUsage.value() ) )
    fileHandle.write( EncodeAsUTF16String( "BatchMode=%s\n" % dialog.batchMode.value()) )
    fileHandle.write( EncodeAsUTF16String( "BatchModeIsMovie=%s\n" % tempIsMovie ) )

    if dialog.separateJobs.value():
        #we need the fullName of the node here, otherwise write nodes that are embedded in groups won't work
        fileHandle.write( EncodeAsUTF16String( "WriteNode=%s\n" % node.fullName() ) )
    elif dialog.separateTasks.value():
        fileHandle.write( EncodeAsUTF16String( "WriteNodesAsSeparateJobs=True\n" ) )

        writeNodeIndex = 0
        for tempNode in writeNodes:
            if not tempNode.knob( 'disable' ).value():
                enterLoop = True
                if dialog.readFileOnly.value() and tempNode.knob( 'reading' ):
                    enterLoop = enterLoop and tempNode.knob( 'reading' ).value()
                if dialog.selectedOnly.value():
                    enterLoop = enterLoop and IsNodeOrParentNodeSelected(tempNode)

                if enterLoop:
                    startFrame = endFrame = None
                    #we need the fullName of the node here, otherwise write nodes that are embedded in groups won't work
                    fileHandle.write( EncodeAsUTF16String( "WriteNode%s=%s\n" % (writeNodeIndex,tempNode.fullName()) ) )
                    if dialog.useNodeRange.value():
                        if tempNode.Class() == "SmartVector" :
                            if tempNode.knob( "render_range" ).value() == "custom":
                                startFrame = int( tempNode.knob( "file.first_frame" ).value() )
                                endFrame = int( tempNode.knob( "file.last_frame" ).value() )
                        else:
                            if tempNode.knob( 'use_limit' ).value():
                                startFrame = int(tempNode.knob('first').value())
                                endFrame = int(tempNode.knob('last').value())

                    if startFrame is None or endFrame is None:
                        startFrame = nuke.Root().firstFrame()
                        endFrame = nuke.Root().lastFrame()
                        if dialog.frameListMode.value() == "Input":
                            try:
                                activeInput = nuke.activeViewer().activeInput()
                                startFrame = nuke.activeViewer().node().input(activeInput).frameRange().first()
                                endFrame = nuke.activeViewer().node().input(activeInput).frameRange().last()
                            except:
                                pass

                    fileHandle.write( EncodeAsUTF16String( "WriteNode%sStartFrame=%s\n" % (writeNodeIndex,startFrame) ) )
                    fileHandle.write( EncodeAsUTF16String( "WriteNode%sEndFrame=%s\n" % (writeNodeIndex,endFrame) ) )
                    writeNodeIndex += 1
    else:
        if dialog.readFileOnly.value() or dialog.selectedOnly.value():
            writeNodesStr = ""

            for tempNode in writeNodes:
                if not tempNode.knob( 'disable' ).value():
                    enterLoop = True
                    if dialog.readFileOnly.value() and tempNode.knob( 'reading' ):
                        enterLoop = enterLoop and tempNode.knob( 'reading' ).value()
                    if dialog.selectedOnly.value():
                        enterLoop = enterLoop and IsNodeOrParentNodeSelected(tempNode)

                    if enterLoop:
                        #we need the fullName of the node here, otherwise write nodes that are embedded in groups won't work
                        writeNodesStr += ("%s," % tempNode.fullName())

            writeNodesStr = writeNodesStr.strip( "," )
            fileHandle.write( EncodeAsUTF16String( "WriteNode=%s\n" % writeNodesStr ) )

    fileHandle.write( EncodeAsUTF16String( "NukeX=%s\n" % dialog.useNukeX.value() ) )

    if int(nuke.env[ 'NukeVersionMajor' ]) >= 7:
        fileHandle.write( EncodeAsUTF16String( "UseGpu=%s\n" % dialog.useGpu.value() ) )

    if int(nuke.env[ 'NukeVersionMajor' ]) >= 8:
        fileHandle.write( EncodeAsUTF16String( "GpuOverride=%s\n" % dialog.chooseGpu.value() ) )

    fileHandle.write( EncodeAsUTF16String( "RenderMode=%s\n" % dialog.renderMode.value() ) )
    fileHandle.write( EncodeAsUTF16String( "EnforceRenderOrder=%s\n" % dialog.enforceRenderOrder.value() ) )
    fileHandle.write( EncodeAsUTF16String( "ContinueOnError=%s\n" % dialog.continueOnError.value() ) )

    if int(nuke.env[ 'NukeVersionMajor' ]) >= 9:
        fileHandle.write( EncodeAsUTF16String( "PerformanceProfiler=%s\n" % dialog.performanceProfiler.value() ) )
        fileHandle.write( EncodeAsUTF16String( "PerformanceProfilerDir=%s\n" % dialog.performanceProfilerPath.value() ) )

    if dialog.chooseViewsToRender.value():
        fileHandle.write( EncodeAsUTF16String( "Views=%s\n" % ','.join(viewsToRender) ) )
    else:
        fileHandle.write( EncodeAsUTF16String( "Views=\n" ) )

    fileHandle.write( EncodeAsUTF16String( "StackSize=%s\n" % dialog.stackSize.value() ))

    fileHandle.close()

    # Update task progress
    progressTask.setMessage("Submitting Job %d to Deadline" % jobCount)
    progressTask.setProgress(30)

    # Submit the job to Deadline
    args = []
    args.append( jobInfoFile.encode(locale.getpreferredencoding() ) )
    args.append( pluginInfoFile.encode(locale.getpreferredencoding() ) )
    if dialog.submitScene.value():
        args.append( root.name() )

    tempResults = ""

    # Submit Job
    progressTask.setProgress(50)

    # If submitting multiple jobs, acquire the semaphore so that only one job is submitted at a time.
    if semaphore:
        semaphore.acquire()

    try:
        tempResults = CallDeadlineCommand( args )
    finally:
        # Release the semaphore if necessary.
        if semaphore:
            semaphore.release()

    # Update task progress
    progressTask.setMessage("Complete!")
    progressTask.setProgress(100)

    print "Job submission #%d complete" % jobCount

    # If submitting multiple jobs, just print the results to the console, otherwise show them to the user.
    if semaphore:
        print tempResults
    else:
        nuke.executeInMainThread( nuke.message, tempResults )

    return tempResults

#This will recursively find nodes of the given class (used to find write nodes, even if they're embedded in groups).
def RecursiveFindNodes(nodeClasses, startNode):
    nodeList = []

    if startNode != None:
        if startNode.Class() in nodeClasses:
            nodeList = [startNode]
        elif isinstance(startNode, nuke.Group):
            for child in startNode.nodes():
                nodeList.extend( RecursiveFindNodes(nodeClasses, child) )

    return nodeList

def RecursiveFindNodesInPrecomp(nodeClasses, startNode):
    nodeList = []

    if startNode != None:
        if startNode.Class() == "Precomp":
            for child in startNode.nodes():
                nodeList.extend( RecursiveFindNodes(nodeClasses, child) )
        elif isinstance(startNode, nuke.Group):
            for child in startNode.nodes():
                nodeList.extend( RecursiveFindNodesInPrecomp(nodeClasses, child) )

    return nodeList

def FindNodesHasNoRenderOrder(nodes):
    noRenderOrderNodes = filter( lambda node:'render_order' not in node.knobs(), nodes ) # loop through all nodes find all nodes doesn't have 'render_order'
    noRenderOrderNodesNames = map( lambda node:node.name(), noRenderOrderNodes ) # loop through nodes in the list created in previous line and collect all names
    return ','.join(noRenderOrderNodesNames), len(noRenderOrderNodesNames) # return the names of nodes in one string and number of nodes

# The main submission function.
def SubmitToDeadline( ):
    global dialog
    global deadlineHome

    # DeadlineGlobals contains initial values for the submission dialog. These can be modified
    # by an external sanity scheck script.
    import DeadlineGlobals

    # Get the root node.
    root = nuke.Root()
    studio = False
    noRoot = False
    if 'studio' in nuke.env.keys() and nuke.env[ 'studio' ]:
        studio = True
    # If the Nuke script hasn't been saved, its name will be 'Root' instead of the file name.
    if root.name() == "Root":
        noRoot = True
        if not studio:
            nuke.message( "The Nuke script must be saved before it can be submitted to Deadline." )
            return

    nuke_projects = []
    valid_projects = []

    if studio:
        #Get the projects and check if we have any comps in any of them
        nuke_projects = hcore.projects()
        if len(nuke_projects) < 1 and not noRoot:
            nuke.message("The Nuke script or Nuke project must be saved before it can be submitted to Deadline.")
            return

        if len(nuke_projects) > 0:
            foundScripts = False
            for project in nuke_projects:
                sequences = project.sequences()
                for sequence in sequences:
                    tracks = sequence.binItem().activeItem().items()
                    for track in tracks:
                        items = track.items()
                        for item in items:
                            if item.isMediaPresent():
                                source = item.source()
                                name = source.mediaSource().filename()
                                if ".nk" in name:
                                    foundScripts = True
                                    break
                        if foundScripts:
                            break
                    if foundScripts:
                        break
                if foundScripts:
                    foundScripts = False
                    valid_projects.append(project)

            if len(valid_projects) < 1 and noRoot:
                nuke.message("The current Nuke project contains no saved comps that can be rendered. Please save any existing Nuke scripts before submitting to Deadline.")
                return

    # If the Nuke script has been modified, then save it.
    if root.modified() and not noRoot:
        if root.name() != "Root":
            nuke.scriptSave( root.name() )

    # Get the current user Deadline home directory, which we'll use to store settings and temp files.
    deadlineHome = CallDeadlineCommand( ["-GetCurrentUserHomeDirectory",] )

    deadlineHome = deadlineHome.replace( "\n", "" ).replace( "\r", "" )
    deadlineSettings = deadlineHome + "/settings"
    deadlineTemp = deadlineHome + "/temp"

    # Get the maximum priority.
    #output = CallDeadlineCommand( ["-getmaximumpriority",] )
    #maximumPriority = int(output)
    # hardcode default value for speed
    maximumPriority = 100

    # Get the pools.
    #output = CallDeadlineCommand( ["-pools",] )
    # hardcode default value for speed
    output = 'none\n'
    pools = output.splitlines()

    secondaryPools = []
    secondaryPools.append(" ")
    for currPool in pools:
        secondaryPools.append(currPool)

    # Get the groups.
    #output = CallDeadlineCommand( ["-groups",] )
    # hardcode default value for speed
    output = 'none\ndesktop\nfarm\n'
    groups = output.splitlines()

    initFrameListMode = "Global"
    initCustomFrameList = None

    # Set initial settings for submission dialog.
    if noRoot:
        DeadlineGlobals.initJobName = "Untitled"
    else:
        DeadlineGlobals.initJobName = os.path.basename( nuke.Root().name() )
    DeadlineGlobals.initComment = ""

    DeadlineGlobals.initDepartment = ""
    DeadlineGlobals.initPool = "none"
    DeadlineGlobals.initSecondaryPool = " "
    DeadlineGlobals.initGroup = "none"
    DeadlineGlobals.initPriority = 50
    DeadlineGlobals.initTaskTimeout = 0
    DeadlineGlobals.initAutoTaskTimeout = False
    DeadlineGlobals.initConcurrentTasks = 1
    DeadlineGlobals.initLimitConcurrentTasks = True
    DeadlineGlobals.initMachineLimit = 0
    DeadlineGlobals.initIsBlacklist = False
    DeadlineGlobals.initMachineList = ""
    DeadlineGlobals.initLimitGroups = ""
    DeadlineGlobals.initDependencies = ""
    DeadlineGlobals.initOnComplete = "Nothing"
    DeadlineGlobals.initSubmitSuspended = False
    DeadlineGlobals.initChunkSize = 10
    DeadlineGlobals.initThreads = 0
    DeadlineGlobals.initMemoryUsage = 0
    DeadlineGlobals.initSeparateJobs = False
    DeadlineGlobals.initSeparateJobDependencies = False
    DeadlineGlobals.initSeparateTasks = False
    DeadlineGlobals.initUseNodeRange = True
    DeadlineGlobals.initReadFileOnly = False
    DeadlineGlobals.initSelectedOnly = False
    DeadlineGlobals.initSubmitScene = False
    DeadlineGlobals.initBatchMode = True
    DeadlineGlobals.initContinueOnError = False
    DeadlineGlobals.initUseGpu = False
    DeadlineGlobals.initChooseGpu = 0
    DeadlineGlobals.initEnforceRenderOrder = False
    DeadlineGlobals.initStackSize = 0
    DeadlineGlobals.initRenderMode = "Use Scene Settings"
    DeadlineGlobals.initPerformanceProfiler = False
    DeadlineGlobals.initReloadPlugin = False
    DeadlineGlobals.initPerformanceProfilerPath = ""
    DeadlineGlobals.initPrecompFirst = False
    DeadlineGlobals.initPrecompOnly = False
    DeadlineGlobals.initSmartVectorOnly = False
    DeadlineGlobals.initExtraInfo0 = ""
    DeadlineGlobals.initExtraInfo1 = ""
    DeadlineGlobals.initExtraInfo2 = ""
    DeadlineGlobals.initExtraInfo3 = ""
    DeadlineGlobals.initExtraInfo4 = ""
    DeadlineGlobals.initExtraInfo5 = ""
    DeadlineGlobals.initExtraInfo6 = ""
    DeadlineGlobals.initExtraInfo7 = ""
    DeadlineGlobals.initExtraInfo8 = ""
    DeadlineGlobals.initExtraInfo9 = ""

    DeadlineGlobals.initUseNukeX = False
    if nuke.env[ 'nukex' ]:
        DeadlineGlobals.initUseNukeX = True

    # Read In Sticky Settings
    configFile = deadlineSettings + "/nuke_py_submission.ini"
    print "Reading sticky settings from %s" % configFile
    try:
        if os.path.isfile( configFile ):
            config = ConfigParser.ConfigParser()
            config.read( configFile )

            if config.has_section( "Sticky" ):
                if config.has_option( "Sticky", "FrameListMode" ):
                    initFrameListMode = config.get( "Sticky", "FrameListMode" )
                if config.has_option( "Sticky", "CustomFrameList" ):
                    initCustomFrameList = config.get( "Sticky", "CustomFrameList" )

                if config.has_option( "Sticky", "Department" ):
                    DeadlineGlobals.initDepartment = config.get( "Sticky", "Department" )
                if config.has_option( "Sticky", "Pool" ):
                    DeadlineGlobals.initPool = config.get( "Sticky", "Pool" )
                if config.has_option( "Sticky", "SecondaryPool" ):
                    DeadlineGlobals.initSecondaryPool = config.get( "Sticky", "SecondaryPool" )
                if config.has_option( "Sticky", "Group" ):
                    DeadlineGlobals.initGroup = config.get( "Sticky", "Group" )
                if config.has_option( "Sticky", "Priority" ):
                    DeadlineGlobals.initPriority = config.getint( "Sticky", "Priority" )
                if config.has_option( "Sticky", "MachineLimit" ):
                    DeadlineGlobals.initMachineLimit = config.getint( "Sticky", "MachineLimit" )
                if config.has_option( "Sticky", "IsBlacklist" ):
                    DeadlineGlobals.initIsBlacklist = config.getboolean( "Sticky", "IsBlacklist" )
                if config.has_option( "Sticky", "MachineList" ):
                    DeadlineGlobals.initMachineList = config.get( "Sticky", "MachineList" )
                if config.has_option( "Sticky", "LimitGroups" ):
                    DeadlineGlobals.initLimitGroups = config.get( "Sticky", "LimitGroups" )
                if config.has_option( "Sticky", "SubmitSuspended" ):
                    DeadlineGlobals.initSubmitSuspended = config.getboolean( "Sticky", "SubmitSuspended" )
                if config.has_option( "Sticky", "ChunkSize" ):
                    DeadlineGlobals.initChunkSize = config.getint( "Sticky", "ChunkSize" )
                if config.has_option( "Sticky", "ConcurrentTasks" ):
                    DeadlineGlobals.initConcurrentTasks = config.getint( "Sticky", "ConcurrentTasks" )
                if config.has_option( "Sticky", "LimitConcurrentTasks" ):
                    DeadlineGlobals.initLimitConcurrentTasks = config.getboolean( "Sticky", "LimitConcurrentTasks" )
                if config.has_option( "Sticky", "Threads" ):
                    DeadlineGlobals.initThreads = config.getint( "Sticky", "Threads" )
                if config.has_option( "Sticky", "SubmitScene" ):
                    DeadlineGlobals.initSubmitScene = config.getboolean( "Sticky", "SubmitScene" )
                if config.has_option( "Sticky", "BatchMode" ):
                    DeadlineGlobals.initBatchMode = config.getboolean( "Sticky", "BatchMode" )
                if config.has_option( "Sticky", "ContinueOnError" ):
                    DeadlineGlobals.initContinueOnError = config.getboolean( "Sticky", "ContinueOnError" )
                if config.has_option( "Sticky", "UseNodeRange" ):
                    DeadlineGlobals.initUseNodeRange = config.getboolean( "Sticky", "UseNodeRange" )
                if config.has_option( "Sticky", "UseGpu" ):
                    DeadlineGlobals.initUseGpu = config.getboolean( "Sticky", "UseGpu" )
                if config.has_option( "Sticky", "ChooseGpu" ):
                    DeadlineGlobals.initChooseGpu = config.getint( "Sticky", "ChooseGpu" )
                if config.has_option( "Sticky", "EnforceRenderOrder" ):
                    DeadlineGlobals.initEnforceRenderOrder = config.getboolean( "Sticky", "EnforceRenderOrder" )
                if config.has_option( "Sticky", "RenderMode" ):
                    DeadlineGlobals.initRenderMode = config.get( "Sticky", "RenderMode" )
                if config.has_option( "Sticky", "PerformanceProfiler" ):
                    DeadlineGlobals.initPerformanceProfiler = config.getboolean( "Sticky", "PerformanceProfiler")
                if config.has_option( "Sticky", "ReloadPlugin" ):
                    DeadlineGlobals.initReloadPlugin = config.getboolean( "Sticky", "ReloadPlugin" )
                if config.has_option( "Sticky", "PerformanceProfilerPath" ):
                    DeadlineGlobals.initPerformanceProfilerPath = config.get( "Sticky", "PerformanceProfilerPath" )
                if config.has_option( "Sticky", "PrecompFirst" ):
                    DeadlineGlobals.initPrecompFirst = config.getboolean( "Sticky", "PrecompFirst")
                if config.has_option( "Sticky", "PrecompOnly" ):
                    DeadlineGlobals.initPrecompOnly = config.get( "Sticky", "PrecompOnly" )
                if config.has_option( "Sticky", "SmartVectorOnly" ):
                    DeadlineGlobals.initSmartVectorOnly = config.get( "Sticky", "SmartVectorOnly" )
    except:
        print( "Could not read sticky settings")
        print traceback.format_exc()

    try:
                root = nuke.Root()
                if "FrameListMode" in root.knobs():
                    initFrameListMode = ( root.knob( "FrameListMode" ) ).value()

                if "CustomFrameList" in root.knobs():
                    initCustomFrameList = ( root.knob( "CustomFrameList" ) ).value()

                if "Department" in root.knobs():
                    DeadlineGlobals.initDepartment = ( root.knob( "Department" ) ).value()

                if "Pool" in root.knobs():
                    DeadlineGlobals.initPool = ( root.knob( "Pool" ) ).value()

                if "SecondaryPool" in root.knobs():
                    DeadlineGlobals.initSecondaryPool = ( root.knob( "SecondaryPool" ) ).value()

                if "Group" in root.knobs():
                    DeadlineGlobals.initGroup = ( root.knob( "Group" ) ).value()

                if "Priority" in root.knobs():
                    DeadlineGlobals.initPriority = int( ( root.knob( "Priority" ) ).value() )

                if "MachineLimit" in root.knobs():
                    DeadlineGlobals.initMachineLimit = int( ( root.knob( "MachineLimit" ) ).value() )

                if "IsBlacklist" in root.knobs():
                    DeadlineGlobals.initIsBlacklist = StrToBool( ( root.knob( "IsBlacklist" ) ).value() )

                if "MachineList" in root.knobs():
                    DeadlineGlobals.initMachineList = ( root.knob( "MachineList" ) ).value()

                if "LimitGroups" in root.knobs():
                    DeadlineGlobals.initLimitGroups = ( root.knob( "LimitGroups" ) ).value()

                if "SubmitSuspended" in root.knobs():
                    DeadlineGlobals.initSubmitSuspended = StrToBool( ( root.knob( "SubmitSuspended" ) ).value() )

                if "ChunkSize" in root.knobs():
                    DeadlineGlobals.initChunkSize = int( ( root.knob( "ChunkSize" ) ).value() )

                if "ConcurrentTasks" in root.knobs():
                    DeadlineGlobals.initConcurrentTasks = int( ( root.knob( "ConcurrentTasks" ) ).value() )

                if "LimitConcurrentTasks" in root.knobs():
                    DeadlineGlobals.initLimitConcurrentTasks = StrToBool( ( root.knob( "LimitConcurrentTasks" ) ).value() )

                if "Threads" in root.knobs():
                    DeadlineGlobals.initThreads = int( ( root.knob( "Threads" ) ).value() )

                if "SubmitScene" in root.knobs():
                    DeadlineGlobals.initSubmitScene = StrToBool( ( root.knob( "SubmitScene" ) ).value() )

                if "BatchMode" in root.knobs():
                    DeadlineGlobals.initBatchMode = StrToBool( ( root.knob( "BatchMode" ) ).value() )

                if "ContinueOnError" in root.knobs():
                    DeadlineGlobals.initContinueOnError = StrToBool( ( root.knob( "ContinueOnError" ) ).value() )

                if "UseNodeRange" in root.knobs():
                    DeadlineGlobals.initUseNodeRange = StrToBool( ( root.knob( "UseNodeRange" ) ).value() )

                if "UseGpu" in root.knobs():
                    DeadlineGlobals.initUseGpu = StrToBool( ( root.knob( "UseGpu" ) ).value() )

                if "ChooseGpu" in root.knobs():
                    DeadlineGlobals.initChooseGpu = int( ( root.knob( "ChooseGpu" ) ).value() )

                if "EnforceRenderOrder" in root.knobs():
                    DeadlineGlobals.initEnforceRenderOrder = StrToBool( ( root.knob( "EnforceRenderOrder" ) ).value() )

                if "DeadlineRenderMode" in root.knobs():
                    DeadlineGlobals.initRenderMode = ( root.knob( "DeadlineRenderMode" ) ).getText()

                if "PerformanceProfiler" in root.knobs():
                    DeadlineGlobals.initPerformanceProfiler = StrToBool( ( root.knob( "PerformanceProfiler" ) ).value() )

                if "ReloadPlugin" in root.knobs():
                    DeadlineGlobals.initReloadPlugin = StrToBool( ( root.knob( "ReloadPlugin" ) ).value() )

                if "PerformanceProfilerPath" in root.knobs():
                    DeadlineGlobals.initPerformanceProfilerPath = ( root.knob( "PerformanceProfilerPath" ) ).value()

                if "PrecompFirst" in root.knobs():
                    DeadlineGlobals.initPrecompFirst = ( root.knob( "PrecompFirst" ) ).value()

                if "PrecompOnly" in root.knobs():
                    DeadlineGlobals.initPrecompOnly = ( root.knob( "PrecompOnly" ) ).value()

                if "SmartVectorOnly" in root.knobs():
                    DeadlineGlobals.initSmartVectorOnly = ( root.knob( "SmartVectorOnly" ) ).value()

    except:
        print "Could not read knob settings."
        print traceback.format_exc()

    if initFrameListMode != "Custom":
        startFrame = nuke.Root().firstFrame()
        endFrame = nuke.Root().lastFrame()
        if initFrameListMode == "Input":
            try:
                activeInput = nuke.activeViewer().activeInput()
                startFrame = nuke.activeViewer().node().input(activeInput).frameRange().first()
                endFrame = nuke.activeViewer().node().input(activeInput).frameRange().last()
            except:
                pass

        if startFrame == endFrame:
            DeadlineGlobals.initFrameList = str(startFrame)
        else:
            DeadlineGlobals.initFrameList = str(startFrame) + "-" + str(endFrame)
    else:
        if initCustomFrameList == None or initCustomFrameList.strip() == "":
            startFrame = nuke.Root().firstFrame()
            endFrame = nuke.Root().lastFrame()
            if startFrame == endFrame:
                DeadlineGlobals.initFrameList = str(startFrame)
            else:
                DeadlineGlobals.initFrameList = str(startFrame) + "-" + str(endFrame)
        else:
            DeadlineGlobals.initFrameList = initCustomFrameList.strip()

    # Run the sanity check script if it exists, which can be used to set some initial values.
    try:
        import CustomSanityChecks
        sanityResult = CustomSanityChecks.RunSanityCheck()
        if not sanityResult:
            print( "Sanity check returned false, exiting" )
            return
    except:
        print( "Could not run CustomSanityChecks.py script" )
        print( traceback.format_exc() )

    if DeadlineGlobals.initPriority > maximumPriority:
        DeadlineGlobals.initPriority = (maximumPriority / 2)

    # Both of these can't be enabled!
    if DeadlineGlobals.initSeparateJobs and DeadlineGlobals.initSeparateTasks:
        DeadlineGlobals.initSeparateTasks = False

    extraInfo = [ "" ] * 10
    extraInfo[ 0 ] = DeadlineGlobals.initExtraInfo0
    extraInfo[ 1 ] = DeadlineGlobals.initExtraInfo1
    extraInfo[ 2 ] = DeadlineGlobals.initExtraInfo2
    extraInfo[ 3 ] = DeadlineGlobals.initExtraInfo3
    extraInfo[ 4 ] = DeadlineGlobals.initExtraInfo4
    extraInfo[ 5 ] = DeadlineGlobals.initExtraInfo5
    extraInfo[ 6 ] = DeadlineGlobals.initExtraInfo6
    extraInfo[ 7 ] = DeadlineGlobals.initExtraInfo7
    extraInfo[ 8 ] = DeadlineGlobals.initExtraInfo8
    extraInfo[ 9 ] = DeadlineGlobals.initExtraInfo9


    # Check for potential issues and warn user about any that are found.
    warningMessages = ""
    nodeClasses = [ "Write", "DeepWrite", "WriteGeo" ]
    writeNodes = RecursiveFindNodes( nodeClasses, nuke.Root() )
    precompWriteNodes = RecursiveFindNodesInPrecomp( nodeClasses, nuke.Root() )
    smartVectorNodes = RecursiveFindNodes( "SmartVector", nuke.Root() )

    print "Found a total of %d write nodes" % len( writeNodes )
    print "Found a total of %d write nodes within precomp nodes" % len( precompWriteNodes )
    print "Found a total of %d nodes within smart vector nodes" % len( smartVectorNodes )

    # Check all the output filenames if they are local or not padded (non-movie files only).
    outputCount = 0

    for node in writeNodes:
        reading = False
        if node.knob( 'reading' ):
            reading = node.knob( 'reading' ).value()

        # Need at least one write node that is enabled, and not set to read in as well.
        if not node.knob( 'disable' ).value() and not reading:
            outputCount = outputCount + 1

            # if root.proxy() and node.knob( 'proxy' ).value() != "":
                # filename = node.knob( 'proxy' ).value()
            # else:
                # filename = node.knob( 'file' ).value()

            #nuke.filename will evaluate embedded TCL, but leave the frame padding
            filename = nuke.filename(node)

            if filename == "":
                warningMessages = warningMessages + "No output path for write node '" + node.name() + "' is defined\n\n"
            else:
                fileType = node.knob( 'file_type' ).value()

                if filename == None:
                    warningMessages = warningMessages + "Output path for write node '" + node.name() + "' is empty\n\n"
                else:
                    if IsPathLocal( filename ):
                        warningMessages = warningMessages + "Output path for write node '" + node.name() + "' is local:\n" + filename + "\n\n"
                    if not HasExtension( filename ) and fileType.strip() == "":
                        warningMessages = warningMessages + "Output path for write node '%s' has no extension:\n%s\n\n"  % (node.name(), filename)
                    if not IsMovie( filename ) and not IsPadded( os.path.basename( filename ) ):
                        warningMessages = warningMessages + "Output path for write node '" + node.name() + "' is not padded:\n" + filename + "\n\n"

    # Warn if there are no write nodes.
    if outputCount == 0 and not noRoot:
        warningMessages = warningMessages + "At least one enabled write node that has 'read file' disabled is required to render\n\n"

    if len(nuke.views())  == 0:
        warningMessages = warningMessages + "At least one view is required to render\n\n"

    # If there are any warning messages, show them to the user.
    if warningMessages != "":
        warningMessages = warningMessages + "Do you still wish to submit this job to Deadline?"
        answer = nuke.ask( warningMessages )
        if not answer:
            return

    print "Creating submission dialog..."

    # Create an instance of the submission dialog.
    if len(valid_projects) > 0:
        dialog = DeadlineContainerDialog( maximumPriority, pools, secondaryPools, groups, valid_projects, not noRoot )
    else:
        dialog = DeadlineDialog( maximumPriority, pools, secondaryPools, groups )

    # Set the initial values.
    dialog.jobName.setValue( DeadlineGlobals.initJobName )
    dialog.comment.setValue( DeadlineGlobals.initComment )
    dialog.department.setValue( DeadlineGlobals.initDepartment )

    dialog.pool.setValue( DeadlineGlobals.initPool )
    dialog.secondaryPool.setValue( DeadlineGlobals.initSecondaryPool )
    dialog.group.setValue( DeadlineGlobals.initGroup )
    dialog.priority.setValue( DeadlineGlobals.initPriority )
    dialog.taskTimeout.setValue( DeadlineGlobals.initTaskTimeout )
    dialog.autoTaskTimeout.setValue( DeadlineGlobals.initAutoTaskTimeout )
    dialog.concurrentTasks.setValue( DeadlineGlobals.initConcurrentTasks )
    dialog.limitConcurrentTasks.setValue( DeadlineGlobals.initLimitConcurrentTasks )
    dialog.machineLimit.setValue( DeadlineGlobals.initMachineLimit )
    dialog.isBlacklist.setValue( DeadlineGlobals.initIsBlacklist )
    dialog.machineList.setValue( DeadlineGlobals.initMachineList )
    dialog.limitGroups.setValue( DeadlineGlobals.initLimitGroups )
    dialog.dependencies.setValue( DeadlineGlobals.initDependencies )
    dialog.onComplete.setValue( DeadlineGlobals.initOnComplete )
    dialog.submitSuspended.setValue( DeadlineGlobals.initSubmitSuspended )

    dialog.frameListMode.setValue( initFrameListMode )
    dialog.frameList.setValue( DeadlineGlobals.initFrameList )
    dialog.chunkSize.setValue( DeadlineGlobals.initChunkSize )
    dialog.threads.setValue( DeadlineGlobals.initThreads )
    dialog.memoryUsage.setValue( DeadlineGlobals.initMemoryUsage )
    dialog.separateJobs.setValue( DeadlineGlobals.initSeparateJobs )
    dialog.separateJobDependencies.setValue( DeadlineGlobals.initSeparateJobDependencies )
    dialog.separateTasks.setValue( DeadlineGlobals.initSeparateTasks )
    dialog.readFileOnly.setValue( DeadlineGlobals.initReadFileOnly )
    dialog.selectedOnly.setValue( DeadlineGlobals.initSelectedOnly )
    dialog.submitScene.setValue( DeadlineGlobals.initSubmitScene )
    dialog.useNukeX.setValue( DeadlineGlobals.initUseNukeX )
    dialog.continueOnError.setValue( DeadlineGlobals.initContinueOnError )
    dialog.batchMode.setValue( DeadlineGlobals.initBatchMode )
    dialog.useNodeRange.setValue( DeadlineGlobals.initUseNodeRange )
    dialog.useGpu.setValue( DeadlineGlobals.initUseGpu )
    dialog.chooseGpu.setValue( DeadlineGlobals.initChooseGpu )
    dialog.enforceRenderOrder.setValue( DeadlineGlobals.initEnforceRenderOrder )
    dialog.renderMode.setValue( DeadlineGlobals.initRenderMode )
    dialog.performanceProfiler.setValue( DeadlineGlobals.initPerformanceProfiler )
    dialog.reloadPlugin.setValue( DeadlineGlobals.initReloadPlugin )
    dialog.performanceProfilerPath.setValue( DeadlineGlobals.initPerformanceProfilerPath )
    dialog.precompFirst.setValue( DeadlineGlobals.initPrecompFirst )
    dialog.precompOnly.setValue( DeadlineGlobals.initPrecompOnly )
    dialog.smartVectorOnly.setValue( DeadlineGlobals.initSmartVectorOnly )
    #dialog.viewsToRender.setValue( DeadlineGlobals.initViews )
    dialog.stackSize.setValue( DeadlineGlobals.initStackSize )

    dialog.separateJobs.setEnabled( len( writeNodes ) > 0 )
    dialog.separateTasks.setEnabled( len( writeNodes ) > 0 )

    dialog.separateJobDependencies.setEnabled( dialog.separateJobs.value() )
    dialog.useNodeRange.setEnabled( dialog.separateJobs.value() or dialog.separateTasks.value() )
    dialog.precompFirst.setEnabled( dialog.separateJobs.value() or dialog.separateTasks.value() )
    dialog.precompOnly.setEnabled( dialog.separateJobs.value() or dialog.separateTasks.value() )
    dialog.smartVectorOnly.setEnabled( dialog.separateJobs.value() or dialog.separateTasks.value() )
    dialog.frameList.setEnabled( not (dialog.separateJobs.value() and dialog.useNodeRange.value()) and not dialog.separateTasks.value() )

    # Show the dialog.
    success = False
    while not success:
        success = dialog.ShowDialog()
        if not success:
            WriteStickySettings( dialog, configFile )
            return

        errorMessages = ""
        warningMessages = ""

        # Check that frame range is valid.
        if dialog.frameList.value().strip() == "":
            errorMessages = errorMessages + "No frame list has been specified.\n\n"

        # If submitting separate write nodes, make sure there are jobs to submit
        if dialog.readFileOnly.value() or dialog.selectedOnly.value():
            validNodeFound = False
            if not dialog.precompOnly.value():
                for node in writeNodes:
                    if not node.knob( 'disable' ).value():
                        validNodeFound = True
                        if dialog.readFileOnly.value():
                            if node.knob( 'reading' ) and not node.knob( 'reading' ).value():
                                validNodeFound = False
                        if dialog.selectedOnly.value() and not IsNodeOrParentNodeSelected(node):
                            validNodeFound = False

                        if validNodeFound:
                            break
            else:
                for node in precompWriteNodes:
                    if not node.knob( 'disable' ).value():
                        validNodeFound = True
                        if dialog.readFileOnly.value():
                            if node.knob( 'reading' ) and not node.knob( 'reading' ).value():
                                validNodeFound = False
                        if dialog.selectedOnly.value() and not IsNodeOrParentNodeSelected(node):
                            validNodeFound = False

                        if validNodeFound:
                            break

            if not validNodeFound:
                if dialog.readFileOnly.value() and dialog.selectedOnly.value():
                    errorMessages = errorMessages + "There are no selected write nodes with 'Read File' enabled, so there are no jobs to submit.\n\n"
                elif dialog.readFileOnly.value():
                    errorMessages = errorMessages + "There are no write nodes with 'Read File' enabled, so there are no jobs to submit.\n\n"
                elif dialog.selectedOnly.value():
                    errorMessages = errorMessages + "There are no selected write nodes, so there are no jobs to submit.\n\n"

        if dialog.smartVectorOnly.value() and len( smartVectorNodes ) == 0:
            errorMessages = errorMessages + "There are no smart vector nodes, so there are no jobs to submit.\n\n"

        # Check if at least one view has been selected.
        if dialog.chooseViewsToRender.value():
            viewCount = 0
            for vk in dialog.viewToRenderKnobs:
                if vk[0].value():
                    viewCount = viewCount + 1

            if viewCount == 0:
                errorMessages = errorMessages + "There are no views selected.\n\n"

        if len(valid_projects) > 0:
            #We need to check if there is a root comp, or if sequences have been specified
            if noRoot and not dialog.submitSequenceJobs.value():
                errorMessages = errorMessages + "There is no saved comp selected in the node graph and Sequence Job Submission is disabled.\n\n"

            elif noRoot and dialog.chooseCompsToRender.value():
                #Check if any sequences were selected
                found = False
                for knob in dialog.sequenceKnobs:
                    if knob[0].value() and knob[1][1] == dialog.studioProject.value():
                        found = True
                        break

                if not found:
                    errorMessages = errorMessages + "Sequence Job Submission and Choose Sequences To Render are enabled but no sequences have been selected. Please select some sequences to render or disable Choose Sequences To Render.\n\n"

        # Check if proxy mode is enabled and Render using Proxy Mode is disabled, then warn the user.
        if root.proxy() and dialog.renderMode.value() == "Use Scene Settings":
            warningMessages = warningMessages + "Proxy Mode is enabled and the scene is being rendered using scene settings, which may cause problems when rendering through Deadline.\n\n"

        # Check if the script file is local and not being submitted to Deadline.
        if not dialog.submitScene.value():
            if IsPathLocal( root.name() ):
                warningMessages = warningMessages + "Nuke script path is local and is not being submitted to Deadline:\n" + root.name() + "\n\n"

        # Check Performance Profile Path
        if dialog.performanceProfiler.value():
            if not os.path.exists( dialog.performanceProfilerPath.value() ):
                errorMessages += "Performance Profiler is enabled, but an XML directory has not been selected (or it does not exist). Either select a valid network path, or disable Performance Profiling.\n\n"

        if dialog.separateTasks.value() and dialog.frameListMode.value() == "Custom" and not dialog.useNodeRange.value():
            errorMessages += "Custom frame list is not supported when submitting write nodes as separate tasks. Please choose Global or Input, or enable Use Node's Frame List.\n\n"

        if len(smartVectorNodes) > 0 and not (dialog.separateJobs.value() or  dialog.separateTasks.value()):
            warningMessages += 'This view has Smart Vectors in it. Please make sure that either the Smart Vectors are already rendered or "Submit Write Nodes As Separate Jobs" or "Submit Write Nodes As Separate Tasks For The Same Job" are enabled.\n\n'

        # Alert the user of any errors.
        if errorMessages != "":
            errorMessages = errorMessages + "Please fix these issues and submit again."
            nuke.message( errorMessages )
            success = False

        # Alert the user of any warnings.
        if success and warningMessages != "":
            warningMessages = warningMessages + "Do you still wish to submit this job to Deadline?"
            answer = nuke.ask( warningMessages )
            if not answer:
                WriteStickySettings( dialog, configFile )
                return


    #Save sticky settings
    WriteStickySettings( dialog, configFile )

    tempJobName = dialog.jobName.value()
    tempDependencies = dialog.dependencies.value()
    tempFrameList = dialog.frameList.value().strip()
    tempChunkSize = dialog.chunkSize.value()
    tempIsMovie = False
    semaphore = threading.Semaphore()

    if len(valid_projects) > 0 and dialog.submitSequenceJobs.value():
        SubmitSequenceJobs(dialog, deadlineTemp, tempDependencies, semaphore, extraInfo)
    else:
        # Check if we should be submitting a separate job for each write node.
        if dialog.separateJobs.value():
            jobCount = 0
            previousJobId = ""
            submitThreads = []

            tempwriteNodes = []

            if dialog.selectedOnly.value():
                writeNodes = filter( IsNodeOrParentNodeSelected, writeNodes )

            nodeNames, num = FindNodesHasNoRenderOrder( writeNodes )

            if num > 0 and not nuke.ask( 'No render order nodes found: %s \n\n' % (nodeNames) +
                                        'Do you still wish to submit this job to Deadline?' ):
                return

            if dialog.precompOnly.value():
                tempWriteNodes = sorted( precompWriteNodes, key = lambda node: getRenderOrder( node ) )
            elif dialog.precompFirst.value():
                tempWriteNodes = sorted( precompWriteNodes, key = lambda node: getRenderOrder( node ) )

                additionalNodes = [item for item in writeNodes if item not in precompWriteNodes]
                additionalNodes = sorted( additionalNodes, key = lambda node: getRenderOrder( node ) )
                tempWriteNodes.extend(additionalNodes)
            elif dialog.smartVectorOnly.value():
                tempWriteNodes = smartVectorNodes
            else:
                tempWriteNodes = sorted( writeNodes, key = lambda node: getRenderOrder( node ) )
                smartVectorNodes.extend(tempWriteNodes)
                tempWriteNodes = smartVectorNodes

            for node in tempWriteNodes:
                print "Now processing %s" % node.name()
                #increment job count -- will be used so not all submissions try to write to the same .job files simultaneously
                jobCount += 1

                # Check if we should enter the loop for this node.
                enterLoop = False
                if not node.knob( 'disable' ).value():
                    enterLoop = True
                    if dialog.readFileOnly.value() and node.knob( 'reading' ):
                        enterLoop = enterLoop and node.knob( 'reading' ).value()
                    if dialog.selectedOnly.value():
                        enterLoop = enterLoop and IsNodeOrParentNodeSelected(node)

                if enterLoop:
                    tempJobName = dialog.jobName.value() + " - " + node.name()

                    tempFrameList = None

                    # Check if the write node is overriding the frame range
                    if dialog.useNodeRange.value():
                        if node.Class() == "SmartVector":
                            if node.knob( "render_range" ).value() == "custom":
                                tempFrameList = str( int( node.knob( "file.first_frame" ).value() ) ) + "-" + str( int( node.knob( "file.last_frame" ).value() ) )
                        else:
                            if node.knob( 'use_limit' ).value():
                                tempFrameList = str(int(node.knob('first').value())) + "-" + str(int(node.knob('last').value()))

                    if tempFrameList == None:
                        tempFrameList = dialog.frameList.value().strip()

                    if IsMovie( node.knob( 'file' ).value() ):
                        tempChunkSize = 1000000
                        tempIsMovie = True
                    else:
                        tempChunkSize = dialog.chunkSize.value()
                        tempIsMovie = False

                    #if creating sequential dependencies, parse for JobId to be used for the next Job's dependencies
                    if dialog.separateJobDependencies.value():
                        if jobCount > 1 and not tempDependencies == "":
                            tempDependencies = tempDependencies + "," + previousJobId
                        elif tempDependencies == "":
                            tempDependencies = previousJobId

                        submitJobResults = SubmitJob( dialog, root, node, tempWriteNodes, deadlineTemp, tempJobName, tempFrameList, tempDependencies, tempChunkSize, tempIsMovie, jobCount, semaphore, extraInfo )
                        for line in submitJobResults.splitlines():
                            if line.startswith("JobID="):
                                previousJobId = line[6:]
                                break
                        tempDependencies = dialog.dependencies.value() #reset dependencies
                    else: #Create a new thread to do the submission
                        print "Spawning submission thread #%d..." % jobCount
                        submitThread = threading.Thread( None, SubmitJob, args = ( dialog, root, node, tempWriteNodes, deadlineTemp, tempJobName, tempFrameList, tempDependencies, tempChunkSize, tempIsMovie, jobCount, semaphore, extraInfo ) )
                        submitThread.start()
                        submitThreads.append( submitThread )

            if not dialog.separateJobDependencies.value():
                print "Spawning results thread..."
                resultsThread = threading.Thread( None, WaitForSubmissions, args = ( submitThreads, ) )
                resultsThread.start()

        elif dialog.separateTasks.value():
            #Create a new thread to do the submission
            tempWriteNodes = []
            if dialog.precompOnly.value():
                tempWriteNodes = sorted( precompWriteNodes, key = lambda node: getRenderOrder( node ) )
            elif dialog.precompFirst.value():
                tempWriteNodes = sorted( precompWriteNodes, key = lambda node: getRenderOrder( node ) )
                additionalNodes = [item for item in writeNodes if item not in precompWriteNodes]
                additionalNodes = sorted( additionalNodes, key = lambda node: getRenderOrder( node ) )
                tempWriteNodes = tempWriteNodes.extend(additionalNodes)
            elif dialog.smartVectorOnly.value():
                tempWriteNodes = smartVectorNodes
            else:
                tempWriteNodes = sorted( writeNodes, key = lambda node: getRenderOrder( node ) )
                smartVectorNodes.extend(tempWriteNodes)
                tempWriteNodes = smartVectorNodes

            print "Spawning submission thread..."
            submitThread = threading.Thread( None, SubmitJob, None, ( dialog, root, None, tempWriteNodes, deadlineTemp, tempJobName, tempFrameList, tempDependencies, tempChunkSize, tempIsMovie, 1, None, extraInfo ) )
            submitThread.start()
        else:
            for tempNode in writeNodes:
                if not tempNode.knob( 'disable' ).value():
                    enterLoop = True
                    if dialog.readFileOnly.value() and tempNode.knob( 'reading' ):
                        enterLoop = enterLoop and tempNode.knob( 'reading' ).value()
                    if dialog.selectedOnly.value():
                        enterLoop = enterLoop and IsNodeOrParentNodeSelected(tempNode)

                    if enterLoop:
                        if IsMovie( tempNode.knob( 'file' ).value() ):
                            tempChunkSize = 1000000
                            tempIsMovie = True
                            break

            smartVectorNodes.extend(writeNodes)
            writeNodes = smartVectorNodes

            #Create a new thread to do the submission
            print "Spawning submission thread..."
            submitThread = threading.Thread( None, SubmitJob, None, ( dialog, root, None, writeNodes, deadlineTemp, tempJobName, tempFrameList, tempDependencies, tempChunkSize, tempIsMovie, 1, None, extraInfo ) )
            submitThread.start()

    print "Main Deadline thread exiting"

def getRenderOrder( node ):
    try:
        value = node[ 'render_order' ].value()
    except NameError:
        value = sys.maxint
    return value

def IsNodeOrParentNodeSelected( node ):
    if node.isSelected():
        return True

    parentNode = nuke.toNode( '.'.join( node.fullName().split('.')[:-1] ) )
    if parentNode:
        return IsNodeOrParentNodeSelected( parentNode )

    return False

def WaitForSubmissions( submitThreads ):
    for thread in submitThreads:
        thread.join()

    results = "Job submission complete. See the Script Editor output window for more information."
    nuke.executeInMainThread( nuke.message, results )

    print "Results thread exiting"

def GetRepositoryPath(subdir = None):
    args = [ "-GetRepositoryPath "]
    if subdir != None and subdir != "":
        args.append(subdir)

    path = CallDeadlineCommand( args ).replace("\n","").replace("\r","")
    return path

################################################################################
## DEBUGGING
################################################################################

#~ # Get the repository root
#~ path = GetRepositoryRoot()
#~ if path != "":
    #~ path += "/submission/Nuke/Main"
    #~ path = path.replace( "\\", "/" )

    #~ # Add the path to the system path
    #~ if path not in sys.path :
        #~ print "Appending \"" + path + "\" to system path to import SubmitNukeToDeadline module"
        #~ sys.path.append( path )

    #~ # Call the main function to begin job submission.
    #~ SubmitToDeadline( path )
#~ else:
    #~ nuke.message( "The SubmitNukeToDeadline.py script could not be found in the Deadline Repository. Please make sure that the Deadline Client has been installed on this machine, that the Deadline Client bin folder is set in the DEADLINE_PATH environment variable, and that the Deadline Client has been configured to point to a valid Repository." )

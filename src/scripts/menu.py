import nuke
import deadline

# The global umedia menu needs to be defined at this file, otherwise the menu
# is added as first item of the main menu instead of being the
# last one

# items avaialble under umedia menu
menubar = nuke.menu("Nuke")
umediaMenu = menubar.addMenu('UMedia')
umediaMenu.addCommand('Rendering/Send to the farm....', deadline.Submitter.submit, 'F8')

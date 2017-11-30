import qbs
import qbs.File
import qbs.TextFile
import qbs.FileInfo
import "installExtra/mainGroup.qbs" as MainGroup

Project {
  id: main
  property string name: "nuke"
  property string releaseType
  property int nukeMajorVersion

  Probe {
    id: info
    property string fileName: "info.json"
    property var data
    configure: {
      // making sure the info file exists
      if (!File.exists(fileName)){
        throw new Error("Cannot find: " + fileName)
      }

      // parsing info contents
      data = JSON.parse(new TextFile(fileName).readAll())
      return data
    }
  }

  Application {
    name: "defaultnuke11"
    MainGroup {
      name: main.name
      version: info.data.version
      nukeMajorVersion: 11
      releaseType: main.releaseType

      condition: (main.nukeMajorVersion === undefined || main.nukeMajorVersion == nukeMajorVersion)
    }
  }

  Application {
    name: "defaultnuke10"
    MainGroup {
      name: main.name
      version: info.data.version
      nukeMajorVersion: 10
      releaseType: main.releaseType

      condition: (main.nukeMajorVersion === undefined || main.nukeMajorVersion == nukeMajorVersion)
    }
  }
}

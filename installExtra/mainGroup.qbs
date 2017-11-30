import qbs
import qbs.FileInfo

Group {
  property string name
  property string version
  property int nukeMajorVersion
  property string releaseType

  qbs.installPrefix: {

    // only processing this information when it's going to be used, otherwise
    // returning
    if (!condition)
      return;

    // building the target location
    targetPrefix = FileInfo.joinPaths("tools", name, version, nukeMajorVersion, "python")

    // making sure to never override a production release
    targetFullPath = FileInfo.joinPaths(qbs.installRoot, targetPrefix)
    if (releaseType == "production" && File.exists(targetFullPath)) {
      throw new Error("Cannot override an existent production release: " + targetFullPath)
    }
    console.info("Target: " + targetFullPath)

    return targetPrefix
  }

  Group {
      name: "Main source files"
      files: [
        "../src/**"
      ]
      excludeFiles: []
      qbs.installSourceBase: "./src"
      qbs.install: true
  }

  Group {
      name: "Info File"
      files: [
        "../info.json"
      ]
      qbs.install: true
      qbs.installSourceBase: "./"
  }
}

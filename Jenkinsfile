main()

def main() {
  timeout(time: 45, unit: 'MINUTES') {
    node('master') {
      try {
        setupProperties()
        runPipeline()
      } catch (err) {
        currentBuild.result = 'FAILURE'
        throw err
      } finally {
        postBuildActions()
      }
    }
  }
}

def setupProperties() {
  // set the TERM env var so colors show up
  env.TERM = 'xterm'
  properties([
    buildDiscarder(logRotator(daysToKeepStr: '30')),
    disableConcurrentBuilds(),
    //run every 15th minute (e.g. 10:45 am)
    pipelineTriggers([cron('H/15 * * * *')])
  ])
}

def runPipeline() {
    def pythonVersion = ""
    stage('Checkout') { 
      checkout scm 
      pythonVersion = readFile('.python-version').trim()
    }
    def stepDefs = [
      [name:'Jenkinsfile',  command:'make test-jenkinsfile'],
      [name:'Setup',        command:'make setup'],
      [name:'Lint',         command:'make lint'],
      [name:'Test',         command:'make test'],
      [name:'Run',          command:'make run'],
    ]
    stepDefs.each { stepDef ->
      stage(stepDef.name) {
        step = makeStep(stepDef)
        step(pythonVersion)
      }
    }
}

// returns a closure to be invoked
def makeStep(stepDef) {
  return { pythonVersion ->
    try {
      withPyenv(pythonVersion) {
        sh stepDef.command
      }
    } catch (err) {
      currentBuild.result = 'FAILURE'
      throw err
    }
  }
}

def postBuildActions() {
  echo "Running post build actions"
  try {
    String currentResult = currentBuild.result ?: 'SUCCESS'
    String previousResult = currentBuild.previousBuild.result ?: 'SUCCESS'
    def channel = "#alerts-git-auto-merge"
    if (previousResult != currentResult) {
      if (currentResult == 'FAILURE') {
        echo "Build failure"
        def message = ("Build failed: ${env.JOB_NAME} "
          + "${env.BUILD_NUMBER} (<${env.RUN_DISPLAY_URL}/|Open>)")
        if (fileExists("reports/errors.txt")) {
          message += "\n" + readFile("reports/errors.txt")
        }
        echo message
        slackSend channel: channel, color: "danger",  message: message
      } else {
        message = ("Build fixed: ${env.JOB_NAME} "
            + "${env.BUILD_NUMBER} (<${env.RUN_DISPLAY_URL}/|Open>)")
        slackSend channel: channel, color: "good",  message: message
      }
    } else {
      echo "previous/current build status equal: ${previousResult}"
    }
  } catch (err) {
    throw err
  } finally {
    // any cleanup?
  }
}

class JenkinsFileTest extends GroovyTestCase {

    void testSuccess() {
        def jenkinsPipeline = getJenkinsPipeline()
        jenkinsPipeline.metaClass.currentBuild = [
            result: "SUCCESS",
            previousBuild: [
                result: "FAILURE"
            ]
        ]
        captureStdOut() {  buffer ->
            jenkinsPipeline.main()
            def actual = buffer.toString()
            assertEquals expectedSuccess, actual
        }
    }

    void testFailure() {
        def jenkinsPipeline = getJenkinsPipeline()
        jenkinsPipeline.metaClass.currentBuild = [
            result: "FAILURE",
            previousBuild: [
                result: "SUCCESS"
            ]
        ]
        captureStdOut() { buffer ->
            jenkinsPipeline.main()
            def actual = buffer.toString()
            assertEquals expectedFailure, actual
        }
    }

    void testException() {
        def jenkinsPipeline = getJenkinsPipeline()
        jenkinsPipeline.metaClass.sh = { command -> 
            println("Running sh command: ${command}")
            throw new Exception("asdf")
        }
        jenkinsPipeline.metaClass.currentBuild = [
            result: "FAILURE",
            previousBuild: [
                result: "SUCCESS"
            ]
        ]
        captureStdOut() { buffer ->
            shouldFail Exception, {
                jenkinsPipeline.main()
            }
            def actual = buffer.toString()
            assertEquals expectedError, actual
        }
    }

    def getJenkinsPipeline() {
        def shell = new GroovyShell()
        def jenkinsPipeline = shell.parse(new File('Jenkinsfile'))
        stubJenkinsApi(jenkinsPipeline)
        return jenkinsPipeline
    }

    def captureStdOut(func) {
        def oldOut = System.out
        def buffer = new ByteArrayOutputStream()
        def newOut = new PrintStream(buffer)
        System.out = newOut
        func(buffer)
        System.out = oldOut
    }

    def stubJenkinsApi(jenkinsPipeline) {
        jenkinsPipeline.metaClass.buildDiscarder = { args -> }
        jenkinsPipeline.metaClass.checkout = { args -> }
        jenkinsPipeline.metaClass.cron = {}
        jenkinsPipeline.metaClass.currentBuild = [
            result: "SUCCESS",
            previousBuild: [result: "SUCCESS"],
        ]
        jenkinsPipeline.metaClass.disableConcurrentBuilds = {}
        jenkinsPipeline.metaClass.echo = { message -> println(message) }
        jenkinsPipeline.metaClass.env = [
            JOB_NAME:"asdf",
            BUILD_NUMBER:"1",
            RUN_DISPLAY_URL:"asdf2",
        ]
        jenkinsPipeline.metaClass.fileExists = { path ->
            return new File(path).exists()
        }
        jenkinsPipeline.metaClass.logRotator = { args -> 
            println("Setting log rotate to ${args.daysToKeepStr} days") 
        }
        jenkinsPipeline.metaClass.node = { name = "default" , func -> 
            println("Running on node ${name}"); func() 
        }
        jenkinsPipeline.metaClass.pipelineTriggers = {}
        jenkinsPipeline.metaClass.pipelineTriggers = {}
        jenkinsPipeline.metaClass.properties = {}
        jenkinsPipeline.metaClass.readFile = { path ->
            return new File(path).getText().trim()
        }
        jenkinsPipeline.metaClass.scm = [:]
        jenkinsPipeline.metaClass.sh = { command -> 
            println("Running sh command: ${command}")
        }
        jenkinsPipeline.metaClass.slackSend = { args ->
            println ("slackSend channel:${args.channel} " 
             + "message:${args.message} color:${args.color}")
        }
        jenkinsPipeline.metaClass.stage = { name , func -> 
            println("Running stage: ${name}"); func() 
        }
        jenkinsPipeline.metaClass.timeout = { args, func -> 
            println("Setting timeout to ${args.time} ${args.unit}"); func() 
        }
        jenkinsPipeline.metaClass.withPyenv = {verison, func -> func()}
        jenkinsPipeline.metaClass.writeFile = { path, text -> 
            new File(path) << text
        }
    }

    def expectedSuccess = """\
        Setting timeout to 45 MINUTES
        Running on node master
        Setting log rotate to 30 days
        Running stage: Checkout
        Running stage: Jenkinsfile
        Running sh command: make test-jenkinsfile
        Running stage: Setup
        Running sh command: make setup
        Running stage: Lint
        Running sh command: make lint
        Running stage: Test
        Running sh command: make test
        Running stage: Run
        Running sh command: make run
        Running post build actions
        slackSend channel:#alerts-git-auto-merge message:Build fixed: asdf 1 (<asdf2/|Open>) color:good
        """.stripIndent()

    def expectedFailure = """\
        Setting timeout to 45 MINUTES
        Running on node master
        Setting log rotate to 30 days
        Running stage: Checkout
        Running stage: Jenkinsfile
        Running sh command: make test-jenkinsfile
        Running stage: Setup
        Running sh command: make setup
        Running stage: Lint
        Running sh command: make lint
        Running stage: Test
        Running sh command: make test
        Running stage: Run
        Running sh command: make run
        Running post build actions
        Build failure
        Build failed: asdf 1 (<asdf2/|Open>)
        slackSend channel:#alerts-git-auto-merge message:Build failed: asdf 1 (<asdf2/|Open>) color:danger
        """.stripIndent()

    def expectedError = """\
        Setting timeout to 45 MINUTES
        Running on node master
        Setting log rotate to 30 days
        Running stage: Checkout
        Running stage: Jenkinsfile
        Running sh command: make test-jenkinsfile
        Running post build actions
        Build failure
        Build failed: asdf 1 (<asdf2/|Open>)
        slackSend channel:#alerts-git-auto-merge message:Build failed: asdf 1 (<asdf2/|Open>) color:danger
        """.stripIndent()
}

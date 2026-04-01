pipeline {
    environment {
        DOCKER_BUILDKIT = '1'
        ARTIFACTORY_CREDS = credentials('dte_pipeline_artifactory_login')
        ARTIFACTORY_REPO = 'artifactory-use-auto-images-snapshots.cto.veritas.com'
        IMG_VERSION = sh(script: '''
                git describe --tags --match="APIv*" --abbrev=1 --long \
                | sed -r "s/API(v[^[:space:]]+)-([[:digit:]]+)-g([[:xdigit:]]+)$/\\1.\\2-\\3/"
            ''', returnStdout: true).trim()
    }

    agent {
        label 'linux_build'
    }

    stages {
        stage("Base Image Matrix") {
            matrix {
                axes {
                    axis {
                        name 'PYTHON_VERSION'
                        values '3.9'
                    }
                }
                stages {
                    stage('env') {
                        steps {
                            sh 'printenv'
                        }
                    }
                    stage('Docker build') {
                        steps {
                            sh 'docker build -t vps-backend:${BRANCH_NAME/\\//-}_${BUILD_NUMBER} --target=test .'
                            sh 'docker network create ${BUILD_TAG}'
                        }
                    }
                    stage('Core unit tests') {
                        steps {
                            sh 'docker run --rm vps-backend:${BRANCH_NAME/\\//-}_${BUILD_NUMBER} pytest src/core'
                        }
                    }
                    stage('Server unit tests') {
                        steps {
                            script {
                                // Start a Redis container as a sidecar
                                docker.image('redis:7.2.4-bookworm').withRun("--hostname redis --network ${BUILD_TAG}",
                                        "--appendonly yes --maxmemory 512M --maxmemory-policy volatile-lru") {
                                    // Ping the Redis server to confirm it's running
                                    sh 'docker run --rm --network ${BUILD_TAG} redis:7.2.4-bookworm redis-cli -h redis PING'
                                    // Run the server unit tests
                                    sh 'docker run --rm --network ${BUILD_TAG} -e BROKER="redis://redis" vps-backend:${BRANCH_NAME/\\//-}_${BUILD_NUMBER} pytest src/server'
                                }
                            }
                        }
                    }
                }
            }
        }
        stage("Publish if BRANCH = 'master'") {
            when {
                branch 'master'
            }
            steps {
                sh '''
                    docker login --username $ARTIFACTORY_CREDS_USR \
                                 --password-stdin \
                                 $ARTIFACTORY_REPO <<< $ARTIFACTORY_CREDS_PSW
                '''
                sh '''
                    docker build --tag $ARTIFACTORY_REPO/vps-backend:latest \
                                 --tag $ARTIFACTORY_REPO/vps-backend:$IMG_VERSION \
                                 --label "VERSION=$IMG_VERSION" \
                                 --label "GIT_COMMIT=$GIT_COMMIT" \
                                 --label "BUILD_TAG=$BUILD_TAG" \
                                 --target=deploy .
                '''
                sh 'docker push --quiet $ARTIFACTORY_REPO/vps-backend:$IMG_VERSION'
                sh 'docker push --quiet $ARTIFACTORY_REPO/vps-backend:latest'
            }
        }
    }
    post {
        always {
            sh 'docker network rm ${BUILD_TAG}'
        }
    }
}
pipeline {
    agent any
    stages {
        stage('Install') {
            steps { bat 'pip install -r requirements.txt' }
        }
        stage('Self Tests') {
            steps { bat 'python -m pytest tests -v --junitxml=reports/junit-self.xml' }
        }
        stage('API Suite') {
            steps { bat 'python -m pytest -m suite -v --junitxml=reports/junit-suite.xml' }
        }
        stage('Quality Gate') {
            steps {
                bat 'python scripts/quality_gate.py reports/junit-suite.xml --min-rate 1.0'
            }
        }
    }
    post {
        always { archiveArtifacts 'reports/**' }
    }
}

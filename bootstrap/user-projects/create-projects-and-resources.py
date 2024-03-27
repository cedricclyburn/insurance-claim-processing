import yaml
from argparse import ArgumentParser


def main():
    arguments = _read_arguments()
    user_count = arguments.user_count
    output_file_path = arguments.output_file_path
    generate_manifest(user_count, output_file_path)


def _read_arguments():
    parser = ArgumentParser()
    parser.add_argument('--user_count', type=int)
    parser.add_argument('--output_file_path', default='user_manifests.yaml')
    arguments = parser.parse_args()
    return arguments


def generate_manifest(user_count, output_file_path):
    resources = _get_overall_resources(user_count)

    manifests = [
        yaml.dump(resource) if type(resource) is dict else resource for resource in resources 
    ]
    overall_manifest = ''
    for manifest in manifests:
        overall_manifest += manifest
        overall_manifest += '---\n'
    with open(output_file_path, 'w') as outputfile:
        outputfile.write(overall_manifest)
    print(f'Wrote manifest {output_file_path}')


def _get_overall_resources(user_count):
    overall_resources = []
    for index in range(1, user_count+1):
        overall_resources += _get_user_resources(f'user{index}')
    return overall_resources


def _get_user_resources(user):
    user_resources = [
        # Set up project
        _get_project_resource(user),
        _get_role_binding_resource(user),
        # Set up minio and data connections
        _get_minio_resource(user),
        # Set up pipeline
        _get_pipelines_definition_resource(user),
    ]
    return user_resources


def _get_minio_resource(user):
    resource = """---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: demo-setup
  namespace: {user}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: demo-setup-edit
  namespace: {user}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: edit
subjects:
- kind: ServiceAccount
  name: demo-setup
---
apiVersion: v1
kind: Service
metadata:
  labels:
    app: minio
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  name: minio
  namespace: {user}
spec:
  ports:
  - name: api
    port: 9000
    targetPort: api
  - name: console
    port: 9090
    targetPort: 9090
  selector:
    app: minio
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  sessionAffinity: None
  type: ClusterIP
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  labels:
    app: minio
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  name: minio
  namespace: {user}
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: minio
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  name: minio
  namespace: {user}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
      app.kubernetes.io/component: minio
      app.kubernetes.io/instance: minio
      app.kubernetes.io/name: minio
      app.kubernetes.io/part-of: minio
      component: minio
  strategy:
    type: Recreate
  template:
    metadata:
      labels:
        app: minio
        app.kubernetes.io/component: minio
        app.kubernetes.io/instance: minio
        app.kubernetes.io/name: minio
        app.kubernetes.io/part-of: minio
        component: minio
    spec:
      containers:
      - args:
        - minio server /data --console-address :9090
        command:
        - /bin/bash
        - -c
        envFrom:
        - secretRef:
            name: minio-root-user
        image: quay.io/minio/minio:latest
        name: minio
        ports:
        - containerPort: 9000
          name: api
          protocol: TCP
        - containerPort: 9090
          name: console
          protocol: TCP
        resources:
          limits:
            cpu: "2"
            memory: 2Gi
          requests:
            cpu: 200m
            memory: 1Gi
        volumeMounts:
        - mountPath: /data
          name: minio
      volumes:
      - name: minio
        persistentVolumeClaim:
          claimName: minio
      - emptyDir: {}
        name: empty
---
apiVersion: batch/v1
kind: Job
metadata:
  name: create-ds-connections
  namespace: {user}
spec:
  selector: {}
  template:
    spec:
      containers:
      - args:
        - -ec
        - |-
          echo -n 'Waiting for minio route'
          while ! oc get route minio-s3 2>/dev/null | grep -qF minio-s3; do
            echo -n .
            sleep 5
          done; echo

          echo -n 'Waiting for minio root user secret'
          while ! oc get secret minio-root-user 2>/dev/null | grep -qF minio-root-user; do
            echo -n .
            sleep 5
          done; echo

          MINIO_ROOT_USER=$(oc get secret minio-root-user -o template --template '{{.data.MINIO_ROOT_USER}}')
          MINIO_ROOT_PASSWORD=$(oc get secret minio-root-user -o template --template '{{.data.MINIO_ROOT_PASSWORD}}')
          MINIO_HOST=https://$(oc get route minio-s3 -o template --template '{{.spec.host}}')

          cat << EOF | oc apply -f-
          apiVersion: v1
          kind: Secret
          metadata:
            annotations:
              opendatahub.io/connection-type: s3
              openshift.io/display-name: My Storage
            labels:
              opendatahub.io/dashboard: "true"
              opendatahub.io/managed: "true"
            name: aws-connection-my-storage
          data:
            AWS_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
            AWS_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
          stringData:
            AWS_DEFAULT_REGION: us-east-1
            AWS_S3_BUCKET: my-storage
            AWS_S3_ENDPOINT: ${MINIO_HOST}
          type: Opaque
          EOF
          cat << EOF | oc apply -f-
          apiVersion: v1
          kind: Secret
          metadata:
            annotations:
              opendatahub.io/connection-type: s3
              openshift.io/display-name: Pipeline Artifacts
            labels:
              opendatahub.io/dashboard: "true"
              opendatahub.io/managed: "true"
            name: aws-connection-pipeline-artifacts
          data:
            AWS_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
            AWS_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
          stringData:
            AWS_DEFAULT_REGION: us-east-1
            AWS_S3_BUCKET: pipeline-artifacts
            AWS_S3_ENDPOINT: ${MINIO_HOST}
          type: Opaque
          EOF
        command:
        - /bin/bash
        image: quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:95b359257a7716b5f8d3a672081a84600218d8f58ca720f46229f7bb893af2ab
        imagePullPolicy: IfNotPresent
        name: create-ds-connections
      restartPolicy: Never
      serviceAccount: demo-setup
      serviceAccountName: demo-setup
---
apiVersion: batch/v1
kind: Job
metadata:
  labels:
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  name: create-minio-buckets
  namespace: {user}
spec:
  selector: {}
  template:
    metadata:
      labels:
        app.kubernetes.io/component: minio
        app.kubernetes.io/instance: minio
        app.kubernetes.io/name: minio
        app.kubernetes.io/part-of: minio
        component: minio
    spec:
      containers:
      - args:
        - -ec
        - |-
          # curl -LO https://ai-on-openshift.io/odh-rhods/img-triton/card.fraud.detection.onnx
          oc get secret minio-root-user
          env | grep MINIO
          cat << 'EOF' | python3
          import boto3, os

          s3 = boto3.client("s3",
                            endpoint_url="http://minio:9000",
                            aws_access_key_id=os.getenv("MINIO_ROOT_USER"),
                            aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD"))
          bucket = 'pipeline-artifacts'
          print('creating pipeline-artifacts bucket')
          if bucket not in [bu["Name"] for bu in s3.list_buckets()["Buckets"]]:
            s3.create_bucket(Bucket=bucket)
          bucket = 'my-storage'
          print('creating my-storage bucket')
          if bucket not in [bu["Name"] for bu in s3.list_buckets()["Buckets"]]:
            s3.create_bucket(Bucket=bucket)
          # filename = "card.fraud.detection.onnx"
          # print('Uploading a model file to it')
          # with open(filename, "rb") as f:
          #   s3.upload_fileobj(f, bucket, f'modelv01/{filename}')
          EOF
        command:
        - /bin/bash
        envFrom:
        - secretRef:
            name: minio-root-user
        image: quay.io/rlundber/sds-small:1.8
        imagePullPolicy: IfNotPresent
        name: create-buckets
      initContainers:
      - args:
        - -ec
        - |-
          echo -n 'Waiting for minio root user secret'
          while ! oc get secret minio-root-user 2>/dev/null | grep -qF minio-root-user; do
          echo -n .
          sleep 5
          done; echo

          echo -n 'Waiting for minio deployment'
          while ! oc get deployment minio 2>/dev/null | grep -qF minio; do
            echo -n .
            sleep 5
          done; echo
          oc wait --for=condition=available --timeout=60s deployment/minio
          sleep 10
        command:
        - /bin/bash
        image: quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:95b359257a7716b5f8d3a672081a84600218d8f58ca720f46229f7bb893af2ab
        imagePullPolicy: IfNotPresent
        name: wait-for-minio
      restartPolicy: Never
      serviceAccount: demo-setup
      serviceAccountName: demo-setup
---
apiVersion: batch/v1
kind: Job
metadata:
  labels:
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  name: create-minio-root-user
  namespace: {user}
spec:
  backoffLimit: 4
  template:
    metadata:
      labels:
        app.kubernetes.io/component: minio
        app.kubernetes.io/instance: minio
        app.kubernetes.io/name: minio
        app.kubernetes.io/part-of: minio
        component: minio
    spec:
      containers:
      - args:
        - -ec
        - |-
          if [ -n "$(oc get secret minio-root-user -oname 2>/dev/null)" ]; then
            echo "Secret already exists. Skipping." >&2
            exit 0
          fi
          genpass() {
              < /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c"${1:-32}"
          }
          id=$(genpass 16)
          secret=$(genpass)
          cat << EOF | oc apply -f-
          apiVersion: v1
          kind: Secret
          metadata:
            name: minio-root-user
          type: Opaque
          stringData:
            MINIO_ROOT_USER: ${id}
            MINIO_ROOT_PASSWORD: ${secret}
          EOF
        command:
        - /bin/bash
        image: quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:95b359257a7716b5f8d3a672081a84600218d8f58ca720f46229f7bb893af2ab
        imagePullPolicy: IfNotPresent
        name: create-minio-root-user
      restartPolicy: Never
      serviceAccount: demo-setup
      serviceAccountName: demo-setup
---
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  labels:
    app: minio
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  name: minio-console
  namespace: {user}
spec:
  port:
    targetPort: console
  tls:
    insecureEdgeTerminationPolicy: Redirect
    termination: edge
  to:
    kind: Service
    name: minio
    weight: 100
  wildcardPolicy: None
---
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  labels:
    app: minio
    app.kubernetes.io/component: minio
    app.kubernetes.io/instance: minio
    app.kubernetes.io/name: minio
    app.kubernetes.io/part-of: minio
    component: minio
  name: minio-s3
  namespace: {user}
spec:
  port:
    targetPort: api
  tls:
    insecureEdgeTerminationPolicy: Redirect
    termination: edge
  to:
    kind: Service
    name: minio
    weight: 100
  wildcardPolicy: None
""".replace("{user}", user)
    return resource


def _get_project_resource(user):
    project_resource = {
        'kind': 'Project',
        'apiVersion': 'project.openshift.io/v1',
        'metadata': {
            'name': user,
            'labels': {
                'kubernetes.io/metadata.name': user,
                'modelmesh-enabled': 'true',
                'opendatahub.io/dashboard': 'true',
            },
            'annotations': {
                'openshift.io/description': '',
                'openshift.io/display-name': user,
            }
        },
        'spec': {
            'finalizers': ['kubernetes']
        }
    }
    return project_resource


def _get_role_binding_resource(user):
    role_binding_resource = {
        'apiVersion': 'rbac.authorization.k8s.io/v1',
        'kind': 'RoleBinding',
        'metadata': {
            'name': 'admin',
            'namespace': user,
        },
        'subjects': [{
            'kind': 'User',
            'apiGroup': 'rbac.authorization.k8s.io',
            'name': user,
        }],
        'roleRef': {
            'apiGroup': 'rbac.authorization.k8s.io',
            'kind': 'ClusterRole',
            'name': 'admin',
        },
    }
    return role_binding_resource


def _get_pipelines_definition_resource(user):
    pipelines_definition_resource = {
        'apiVersion': 'datasciencepipelinesapplications.opendatahub.io/v1alpha1',
        'kind': 'DataSciencePipelinesApplication',
        'metadata':{
            'finalizers':['datasciencepipelinesapplications.opendatahub.io/finalizer'],
            'name': 'pipelines-definition',
            'namespace': user,
        },
        'spec':{
            'apiServer':{
                'stripEOF': True,
                'dbConfigConMaxLifetimeSec': 120,
                'applyTektonCustomResource': True,
                'deploy': True,
                'enableSamplePipeline': False,
                'autoUpdatePipelineDefaultVersion': True,
                'archiveLogs': False,
                'terminateStatus': 'Cancelled',
                'enableOauth': True,
                'trackArtifacts': True,
                'collectMetrics': True,
                'injectDefaultScript': True,
            },
            'database':{
                'mariaDB':{
                    'deploy': True,
                    'pipelineDBName': 'mlpipeline',
                    'pvcSize': '10Gi',
                    'username': 'mlpipeline',
                }
            },
            'objectStorage':{
                'externalStorage':{
                    'bucket': 'pipeline-artifacts',
                    'host': f'minio.{user}.svc.cluster.local:9000',
                    'port': '',
                    's3CredentialsSecret':{
                        'accessKey': 'AWS_ACCESS_KEY_ID',
                        'secretKey': 'AWS_SECRET_ACCESS_KEY',
                        'secretName': 'aws-connection-pipeline-artifacts',
                    },
                    'scheme': 'http',
                    'secure': False,
                }
            },
            'persistenceAgent':{
                'deploy': True,
                'numWorkers': 2
            },
            'scheduledWorkflow':{
                'cronScheduleTimezone': 'UTC',
                'deploy': True,
            }
        }
    }
    return pipelines_definition_resource

if __name__ == '__main__':
    main()
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
        yaml.dump(resource) for resource in resources
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
        # Set up Minio
        _get_minio_deployment(user),
        # Set up pipeline
        _get_pipeline_data_connection_resource(user),
        #_get_allow_from_all_namespaces_resource(user),
        #_get_allow_from_ingress_namespace_resource(user),
        _get_pipelines_definition_resource(user),
    ]
    return user_resources



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

def _get_minio_deployment(user):
    minio_resource1 = {
        'apiVersion': 'v1',
        'kind': 'ServiceAccount',
        'metadata': {
            'name': 'demo-setup'
        }
    minio_resource2 = {
        'apiVersion': 'rbac.authorization.k8s.io/v1',
        'kind': 'RoleBinding',
        'metadata': {
        name: demo-setup-edit
        roleRef:
        apiGroup: rbac.authorization.k8s.io
        kind: ClusterRole
        name: edit
        subjects:
        - kind: ServiceAccount
            name: demo-setup
        }
    minio_resource3 = {
        apiVersion: batch/v1
        kind: Job
        metadata:
        name: create-s3-storage
        spec:
        selector: {}
        template:
            spec:
            containers:
                - args:
                    - -ec
                    - |-
                    echo -n 'Setting up Minio instance and data connections'
                    oc apply -f https://raw.githubusercontent.com/rh-aiservices-bu/test-drive/main/setup/setup-s3-no-sa.yaml
                command:
                    - /bin/bash
                image: image-registry.openshift-image-registry.svc:5000/openshift/tools:latest
                imagePullPolicy: IfNotPresent
                name: create-s3-storage
            restartPolicy: Never
            serviceAccount: demo-setup
            serviceAccountName: demo-setup
        }

def _get_pipeline_data_connection_resource(user):
    aws_connection_object_detection_resource = {
        'kind': 'Secret',
        'apiVersion': 'v1',
        'metadata':{
            'name': 'aws-connection-object-detection',
            'namespace': user,
            'labels':{
                'opendatahub.io/dashboard': 'true',
                'opendatahub.io/managed': 'true',
            },
            'annotations':{
                'opendatahub.io/connection-type': 's3',
                'openshift.io/display-name': 'object-detection',
            },
        },
        'stringData':{
            'AWS_ACCESS_KEY_ID': 'minio',
            'AWS_DEFAULT_REGION': 'us-east-1',
            'AWS_S3_BUCKET': user,
            'AWS_S3_ENDPOINT': 'http://minio-service.minio.svc:9000',
            'AWS_SECRET_ACCESS_KEY': 'minio123',
            'type': 'Opaque',
        }
    }
    return aws_connection_object_detection_resource


def _get_allow_from_all_namespaces_resource(user):
    allow_from_all_namespaces_resource = {
        'kind': 'NetworkPolicy',
        'apiVersion': 'networking.k8s.io/v1',
        'metadata':{
            'name': 'allow-from-all-namespaces',
            'namespace': user,
        },
        'spec':{
            'podSelector': {},
            'ingress': [{'from': [{'namespaceSelector':{}}]}]
        },
        'policyTypes': ['Ingress']
    }
    return allow_from_all_namespaces_resource


def _get_allow_from_ingress_namespace_resource(user):
    allow_from_ingress_namespace_resource = {
        'kind': 'NetworkPolicy',
        'apiVersion': 'networking.k8s.io/v1',
        'metadata':{
            'name': 'allow-from-ingress-namespace',
            'namespace': user,
        },
        'spec':{
            'podSelector': {},
            'ingress': [{
                'from': [{
                    'namespaceSelector': {
                        'matchLabels': {
                            'network-policy': 'global'
                        }
                    }
                }]
            }],
            'policyTypes': ['Ingress'],
        }
    }
    return allow_from_ingress_namespace_resource


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
                    'bucket': 'object-detection-pipelines',
                    'host': 'minio-service.minio.svc:9000',
                    'port': '',
                    's3CredentialsSecret':{
                        'accessKey': 'AWS_ACCESS_KEY_ID',
                        'secretKey': 'AWS_SECRET_ACCESS_KEY',
                        'secretName': 'aws-connection-pipelines',
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
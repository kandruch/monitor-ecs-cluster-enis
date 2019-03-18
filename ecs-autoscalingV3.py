#####################################################################################################################
# A current limitation has been discovered with the ECS platform running in awsvpc mode. When you use                #
# the awsvpc network mode in your task definitions, every task that is launched from that task definition           #
# gets its own elastic network interface, a primary private IP address, and an internal DNS hostname.               #
# The task networking feature simplifies container networking and gives you more control over how                   #
# containerized applications communicate with each other and other services within your VPCs.                       #
#                                                                                                                   #
# The limitation is when your running cluster consumes all of the available ENI's on the hosts for the chosen       #
# instance typeand can no longer provision tasks into the cluster.                                                  #
#                                                                                                                   #
# There is no monitoring available to mitigate this limitation today.                                               #
#                                                                                                                   #
# The code below provides the ability to monitor the ECS cluster CPU, MEM and ENI's and posts custom metrics into   #
# CloudWatch. The overall solution is to setup CloudWatch Events that monitor ECS API calls in the account which    #
# kicks off the Lambda function below to analyze the cluster and report on remaining ENI's in the cluster. If the   #
# desired ENI threshold is reached then the cluster autoscaling group will add an additional host to the cluster    #
# to add new ENI limits to the cluster resource pool.                                                               #
#                                                                                                                   #
# Author: Keith Andruch   <kandruch@amazon.com>                                                                     #
#####################################################################################################################



import boto3
import datetime

# Boto3 AWS Services
cloudwatch = boto3.client('cloudwatch')
ecs = boto3.client('ecs')

# Set True for debugging print outputs
debug_msg = True

# Set variables for ECS Cluster
ecs_cluster_name = "ecs-autoscaling"
eni_supported_per_instance = 8  # use: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html

# Set variables for CloudWatch Metrics
namespace = "AWS/ECS"
dimension1_name = "ecs-autoscaling"
dimension1_value = ecs_cluster_name
timestamp = datetime.datetime.today()
metric_cpu = "ecs-remaining-cpu"
metric_mem = "ecs-remaining-mem"
metric_eni = "ecs-remaining-eni's"


# ECS Cluster Custom Cloudwatch Metric for eni availability, CPU and Memory for automatic scaling of the cluster.

def lambda_handler(event, context):
    # if debug_msg:
    # print("<event>" + str(event) + "</event>")

    # Set variables for ECS Resources
    cluster_available_cpu = 0
    cluster_available_memory = 0
    cluster_remaining_cpu = 0
    cluster_remaining_memory = 0

    # Get cluster's ec2 container instances
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.list_container_instances
    list_container_instances_response = ecs.list_container_instances(
        cluster=ecs_cluster_name,
        status='ACTIVE'
    )

    containerInstanceArns = list_container_instances_response["containerInstanceArns"]
    if debug_msg:
        for instArn in containerInstanceArns:
            print("AmazonResourceName" " = " + instArn)

    # Get number of tasks running in the cluster
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.describe_container_instances
    describe_container_instances_response = ecs.describe_container_instances(
        cluster=ecs_cluster_name,
        containerInstances=containerInstanceArns
    )

    # Get total number of registered elastic network interfaces (eni's) in the cluster
    containerInstances = describe_container_instances_response["containerInstances"]
    number_of_instances = 0
    total_number_of_attached_eni = 0

    # Iterate through the response to calculate the total # of instances with attached eni's
    for instances in containerInstances:
        number_of_instances += 1
        attachments_len = len(instances["attachments"])
        total_number_of_attached_eni += attachments_len

        if debug_msg:
            print("InstanceIds" " = " + instances["ec2InstanceId"] + ":" + str(attachments_len) + " = " "eni's")

    print("Instances with attached eni's" " = " + str(total_number_of_attached_eni))

    # Get registered ECS cluster resources for CPU and MEM
    for containerInstance in describe_container_instances_response['containerInstances']:
        for registeredResource in containerInstance['registeredResources']:
            if registeredResource['name'] == 'CPU':
                cluster_available_cpu += registeredResource['integerValue']
            if registeredResource['name'] == 'MEMORY':
                cluster_available_memory += registeredResource['integerValue']

    if debug_msg:
        print("Registered Cluster CPU: " + str(round(cluster_available_cpu / 1024)) + " " + str("Cores"))
        print("Registered Cluster MEMORY: " + str(round(cluster_available_memory / 1024)) + str("GB"))

    # Get remaining ECS cluster resources for CPU and MEM
    for containerInstance in describe_container_instances_response['containerInstances']:
        for remainingResource in containerInstance['remainingResources']:
            if remainingResource['name'] == 'CPU':
                cluster_remaining_cpu += remainingResource['integerValue']
            if remainingResource['name'] == 'MEMORY':
                cluster_remaining_memory += remainingResource['integerValue']

    if debug_msg:
        print("Remaining Cluster CPU: " + str(round(cluster_remaining_cpu / 1024)) + " " + str("Cores"))
        print("Remaining Cluster MEMORY: " + str(round(cluster_remaining_memory / 1024)) + str("GB"))

    # Calculate remaining CPU resources into percentage
    remaining_cpu_percent = (cluster_remaining_cpu / cluster_available_cpu) * 100
    print("Percentage CPU available" + " = " + str(round(remaining_cpu_percent)) + str("%"))

    # Calculate remaining MEMORY resources into percentage
    remaining_mem_percent = (cluster_remaining_memory / cluster_available_memory) * 100
    print("Percentage MEMORY available" + " = " + str(round(remaining_mem_percent)) + str("%"))

    # Calculate eni's available in the cluster; note that one eni is used for host itself
    eni_supported_on_cluster = (eni_supported_per_instance - 1) * number_of_instances
    print("ENI's supported on the cluster" " = " + str(eni_supported_on_cluster))

    eni_available_for_awsvpc_tasks = eni_supported_on_cluster - total_number_of_attached_eni
    print("ENI's available for awsvpc tasks" " = " + str(eni_available_for_awsvpc_tasks))

    create_metric(metric_eni, eni_available_for_awsvpc_tasks)
    create_metric(metric_cpu, remaining_cpu_percent)
    create_metric(metric_mem, remaining_mem_percent)

    return 'complete'


def create_metric(metricName, value):
    cw_response = cloudwatch.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                'MetricName': metricName,
                'Dimensions': [
                    {
                        'Name': dimension1_name,
                        'Value': dimension1_value
                    },
                ],
                'Timestamp': timestamp,
                'Value': value,
                'Unit': 'Count',
                'StorageResolution': 60
            },
        ]
    )
    print("Cloudwatch Results on ENI's" + " = " + str(value))

    if debug_msg:
        print("CloudWatch Response" + " = " + str(cw_response) + "</cw_response>")
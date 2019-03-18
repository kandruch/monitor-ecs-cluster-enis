# Monitor-ECS-Cluster-ENIs

Currently ECS containers launched in “awsvpc” mode require each task to have a dedicated elastic network interface assigned. This creates a provisioning issue on the cluster when the ec2 instance type in the cluster can no longer attach additional interfaces to the tasks once the capacity on the hosts is reached.

To avoid provisioning errors of new tasks on the cluster a custom lambda is created to monitor the ECS cluster ENI’s (Elastic Network Interface). Once a particular threshold is met the cluster will add an additional EC2 instance to the cluster and allow new tasks to be provisioned.

 ![ECS Autoscaling ENI Solution](./monitor-ecs-cluster-enis.png)
# Task Networking: awsvpc mode

The awsvpc network mode for ECS assigns each task a dedicated network interface on the host. This enables each task to have its own elastic network interface, a primary private IP address and an internal DNS hostname. The main benefit here is that it allows each task to be secured using security groups and grants more visibility with network monitoring tools.

https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking.html 

Instructions
------------
Note: the documentation below assumes you have already deployed an ECS cluster in the environment.

1.	Create a CloudWatch rule with the following event pattern.

CloudWatch Event Pattern: 

This CWE rule is designed to analyze all ECS events on the account and trigger a lambda function to post custom CloudWatch metrics for the remaining CPU, MEM, and ENIs on the selected cluster.

```
RULE: ecs-resources-available-on-cluster

{
    "source": [
        "aws.ecs"
    ],
    "detail-type": [
        "ECS Task State Change",
        "ECS Container Instance State Change"
    ]
}
```
2. Create Lambda function for the ECS custom resource monitoring for ENI’s, CPU and MEM on the assigned cluster.

```
ecs-autoscalingV3.py
```
3.	Create a CloudWatch Alarm based on the custom metrics produced by the cluster in the auto scaling-group.
![Custom CloudWatch Alarm](./ecs-cluster-cw.png)

Example:
```
aws cloudwatch put-metric-alarm \
> --alarm-name ecs-eni-monitoring \
> --alarm-description "Alarm when ENI's on cluster only have 2 slots available in the pool" \
> --metric-name ecs-remaining-eni's \
> --namespace AWS/EC2 \
> --dimensions ecs-autoscaling = ecs-autoscaling \
> --statistic Average \
> --dimensions Name=ecs-autoscaling,Value=ecs-autoscaling \
> --period 300 \
> --evaluation-periods 1 \
> --threshold 2 \
> --comparison-operator GreaterThanOrEqualToThreshold \
> --unit count \
> --alarm-actions "arn:aws:autoscaling:ca-central-1:<account#>:scalingPolicy:<id of the policy>:autoScalingGroupName/<Name>:policyName/<Name> 
```
Outcome
-------
You now have the ability to monitor ECS cluster resources and take appropriate actions on available ENI’s, CPU or MEM resources based on your desired needs. More importantly you will no longer run into provisioning issues running in AWSVPC networking mode when no more ENI’s are available in the cluster and the ECS service gets stuck in an endless loop of trying to add a new ENI to the host’s and then removing them over and over.

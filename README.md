# monitor-ecs-cluster-enis

Currently ECS containers launched in “awsvpc” mode require each task to have a dedicated elastic network interface assigned. This creates a provisioning issue on the cluster when the ec2 instance type in the cluster can no longer attach additional interfaces to the tasks once the capacity on the hosts is reached.

To avoid provisioning errors of new tasks on the cluster a custom lambda is created to monitor the ECS cluster ENI’s (Elastic Network Interface). Once a particular threshold is met the cluster will add an additional EC2 instance to the cluster and allow new tasks to be provisioned.

 

Figure 1: ECS autoscaling ENI solution


Task Networking: awsvpc mode

The awsvpc network mode for ECS assigns each task a dedicated network interface on the host. This enables each task to have its own elastic network interface, a primary private IP address and an internal DNS hostname. The main benefit here is that it allows each task to be secured using security groups and grants more visibility with network monitoring tools.

https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking.html 
 

"""Deploy QSEoW Ownership Manager to AWS EC2."""

import boto3
import base64
import time
import os
from pathlib import Path

# AWS Configuration
AWS_REGION = "us-east-1"
INSTANCE_TYPE = "t3.micro"  # Free tier eligible
KEY_NAME = "qseow-ownership-manager-key"
SECURITY_GROUP_NAME = "qseow-ownership-manager-sg"
INSTANCE_NAME = "qseow-ownership-manager"

# Get credentials from environment (required)
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    print("ERROR: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in environment")
    print("Set them using:")
    print("  export AWS_ACCESS_KEY_ID=your_access_key")
    print("  export AWS_SECRET_ACCESS_KEY=your_secret_key")
    exit(1)


def get_latest_amazon_linux_ami(ec2_client):
    """Get the latest Amazon Linux 2023 AMI ID."""
    response = ec2_client.describe_images(
        Owners=["amazon"],
        Filters=[
            {"Name": "name", "Values": ["al2023-ami-2023*-x86_64"]},
            {"Name": "state", "Values": ["available"]},
            {"Name": "architecture", "Values": ["x86_64"]},
        ],
    )
    images = sorted(response["Images"], key=lambda x: x["CreationDate"], reverse=True)
    return images[0]["ImageId"] if images else None


def create_security_group(ec2_client, vpc_id):
    """Create security group for the application."""
    try:
        response = ec2_client.create_security_group(
            GroupName=SECURITY_GROUP_NAME,
            Description="Security group for QSEoW Ownership Manager",
            VpcId=vpc_id,
        )
        sg_id = response["GroupId"]
        print(f"Created security group: {sg_id}")

        # Add inbound rules
        ec2_client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                # SSH
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}],
                },
                # HTTP (frontend)
                {
                    "IpProtocol": "tcp",
                    "FromPort": 3000,
                    "ToPort": 3000,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Frontend"}],
                },
                # Backend API
                {
                    "IpProtocol": "tcp",
                    "FromPort": 8000,
                    "ToPort": 8000,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Backend API"}],
                },
            ],
        )
        print("Added security group rules")
        return sg_id

    except ec2_client.exceptions.ClientError as e:
        if "InvalidGroup.Duplicate" in str(e):
            # Security group already exists
            response = ec2_client.describe_security_groups(
                Filters=[{"Name": "group-name", "Values": [SECURITY_GROUP_NAME]}]
            )
            sg_id = response["SecurityGroups"][0]["GroupId"]
            print(f"Using existing security group: {sg_id}")
            return sg_id
        raise


def create_key_pair(ec2_client):
    """Create key pair for SSH access."""
    try:
        response = ec2_client.create_key_pair(KeyName=KEY_NAME)
        key_material = response["KeyMaterial"]

        # Save the private key
        key_path = Path.home() / f"{KEY_NAME}.pem"
        with open(key_path, "w") as f:
            f.write(key_material)
        # On Windows, chmod isn't available; on Linux it would be os.chmod(key_path, 0o400)
        try:
            os.chmod(key_path, 0o400)
        except (OSError, AttributeError):
            pass  # Windows doesn't support chmod
        print(f"Created key pair and saved to: {key_path}")
        return KEY_NAME

    except ec2_client.exceptions.ClientError as e:
        if "InvalidKeyPair.Duplicate" in str(e):
            print(f"Using existing key pair: {KEY_NAME}")
            return KEY_NAME
        raise


def get_user_data():
    """Read and encode user data script."""
    script_dir = Path(__file__).parent
    user_data_path = script_dir / "user-data.sh"

    with open(user_data_path, "r") as f:
        user_data = f.read()

    return base64.b64encode(user_data.encode()).decode()


def deploy():
    """Deploy the application to EC2."""
    print("=" * 60)
    print("Deploying QSEoW Ownership Manager to AWS EC2")
    print("=" * 60)

    # Create boto3 session
    session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION,
    )

    ec2_client = session.client("ec2")
    ec2_resource = session.resource("ec2")

    # Get default VPC
    vpcs = ec2_client.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    if not vpcs["Vpcs"]:
        print("ERROR: No default VPC found. Please create one or specify a VPC ID.")
        return None
    vpc_id = vpcs["Vpcs"][0]["VpcId"]
    print(f"Using VPC: {vpc_id}")

    # Get AMI
    ami_id = get_latest_amazon_linux_ami(ec2_client)
    if not ami_id:
        print("ERROR: Could not find Amazon Linux 2023 AMI")
        return None
    print(f"Using AMI: {ami_id}")

    # Create security group
    sg_id = create_security_group(ec2_client, vpc_id)

    # Create key pair
    key_name = create_key_pair(ec2_client)

    # Get user data
    user_data = get_user_data()

    # Check for existing instance
    existing = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [INSTANCE_NAME]},
            {"Name": "instance-state-name", "Values": ["running", "pending"]},
        ]
    )

    if existing["Reservations"]:
        instance_id = existing["Reservations"][0]["Instances"][0]["InstanceId"]
        public_ip = existing["Reservations"][0]["Instances"][0].get("PublicIpAddress", "pending")
        print(f"\nExisting instance found: {instance_id}")
        print(f"Public IP: {public_ip}")
        return instance_id

    # Launch instance
    print("\nLaunching EC2 instance...")
    instances = ec2_resource.create_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        KeyName=key_name,
        SecurityGroupIds=[sg_id],
        MinCount=1,
        MaxCount=1,
        UserData=user_data,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": INSTANCE_NAME}],
            }
        ],
    )

    instance = instances[0]
    print(f"Instance ID: {instance.id}")

    # Wait for instance to be running
    print("Waiting for instance to start...")
    instance.wait_until_running()
    instance.reload()

    public_ip = instance.public_ip_address
    print(f"\n{'=' * 60}")
    print("DEPLOYMENT SUCCESSFUL!")
    print(f"{'=' * 60}")
    print(f"Instance ID: {instance.id}")
    print(f"Public IP: {public_ip}")
    print(f"SSH: ssh -i ~/{KEY_NAME}.pem ec2-user@{public_ip}")
    print(f"App URL: http://{public_ip}:3000")
    print(f"\nNote: The app may take a few minutes to start after deployment.")
    print(f"Check logs: ssh -i ~/{KEY_NAME}.pem ec2-user@{public_ip} 'sudo cat /var/log/user-data.log'")

    return instance.id


if __name__ == "__main__":
    deploy()

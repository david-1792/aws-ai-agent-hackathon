import boto3

ssm = boto3.client('ssm')

def get_ssm_parameter(name: str, decrypt: bool = True) -> str:
    try:
        return ssm.get_parameter(
            Name=name, 
            WithDecryption=decrypt
        )['Parameter']['Value']
    except ssm.exceptions.ParameterNotFound:
        raise ValueError(f'Missing SSM parameter: {name}')
    
def get_region() -> str:
    return boto3.session.Session().region_name
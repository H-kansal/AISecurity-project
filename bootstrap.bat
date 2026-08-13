@REM The bootstrap script provisions the infrastructure that Terraform itself depends on. It creates a private, encrypted, versioned S3 bucket to store the remote terraform.tfstate file and a DynamoDB table to provide state locking. Once these backend resources exist, terraform init configures Terraform to use them, allowing multiple developers to safely share state and preventing concurrent terraform apply operations from corrupting it."


@echo off
setlocal

set REGION=us-east-1
set BUCKET=research-agent-tfstate-0106
set TABLE=research-agent-tf-locks-0106

echo Creating S3 bucket: %BUCKET% in region: %REGION%

aws s3api create-bucket --bucket %BUCKET% --region %REGION% 2>nul
if %errorlevel% equ 0 (
    echo Bucket created.
) else (
    echo Bucket already exists, continuing.
)

echo Enabling versioning...
aws s3api put-bucket-versioning --bucket %BUCKET% --versioning-configuration Status=Enabled

echo Blocking public access...
aws s3api put-public-access-block --bucket %BUCKET% --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo Enabling server-side encryption...
aws s3api put-bucket-encryption --bucket %BUCKET% --server-side-encryption-configuration "{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}"

echo Creating DynamoDB table for state locking: %TABLE%
aws dynamodb create-table --table-name %TABLE% --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region %REGION% 2>nul
if %errorlevel% equ 0 (
    echo DynamoDB table created.
) else (
    echo DynamoDB table already exists, continuing.
)

echo.
echo Bootstrap complete.
echo   S3 bucket  : %BUCKET% (versioned, encrypted, private)
echo   DynamoDB   : %TABLE% (state locking)
echo.
echo Next step: cd terraform  then  terraform init  then  terraform apply

endlocal

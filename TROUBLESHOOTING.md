# Troubleshooting Guide

## Common Issues and Solutions

### 1. AWS Bedrock Region Error

**Error**: `You must specify a region`

**Solution**: 
- Make sure you have AWS credentials configured
- Set the `AWS_REGION` environment variable (default: `us-east-1`)
- Ensure your AWS account has access to Amazon Bedrock

**Steps**:
1. Create a `.env` file with your AWS credentials:
   ```
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   ```

2. Or configure AWS CLI:
   ```bash
   aws configure
   ```

### 2. Redis Chat History Error

**Error**: `RedisChatMessageHistory.__init__() got an unexpected keyword argument 'password'`

**Solution**: 
- The Redis configuration has been updated to handle authentication properly
- Make sure Redis is running on the configured host and port

### 3. Database Connection Issues

**Error**: Database connection failures

**Solution**:
- Ensure PostgreSQL is running
- Check database credentials in `.env` file
- Verify the database exists and is accessible

### 4. Missing Dependencies

**Error**: Import errors for various packages

**Solution**:
```bash
pip install -r requirements.txt
```

### 5. AWS Bedrock Access

**Error**: Access denied or authentication failures

**Solution**:
- Ensure your AWS account has access to Amazon Bedrock
- Verify your IAM user/role has the necessary permissions
- Check that Bedrock is available in your selected region

## Environment Variables

Create a `.env` file with these variables:

```env
# Database Configuration
DB_HOST=localhost
DB_NAME=hospital
DB_USER=postgres
DB_PASSWORD=postgres
DB_PORT=5432

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key

# Flask Configuration
FLASK_DEBUG=False
```

## Quick Setup

1. Run the setup script:
   ```bash
   python setup_env.py
   ```

2. Edit the `.env` file with your credentials

3. Start the application:
   ```bash
   python main.py
   ```

## Getting Help

If you're still experiencing issues:

1. Check the application logs for detailed error messages
2. Verify all services (PostgreSQL, Redis) are running
3. Ensure all environment variables are properly set
4. Check that your AWS credentials have the necessary permissions 
import { Duration, Stack, StackProps, SymlinkFollowMode, CfnOutput } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as path from "path";

export class StrandsAgentsChatbotAPIGatewayStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const packagingDirectory = path.join(__dirname, "../packaging");

    const zipDependencies = path.join(packagingDirectory, "dependencies.zip");
    const zipApp = path.join(packagingDirectory, "app.zip");

    // Create a lambda layer with dependencies to keep the code readable in the Lambda console
    const dependenciesLayer = new lambda.LayerVersion(this, "DependenciesLayer", {
      code: lambda.Code.fromAsset(zipDependencies),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: "Dependencies for Strands Agents IoT device management chatbot",
    });

    // Define the Lambda function
    const iotAgentFunction = new lambda.Function(this, "AgentLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      functionName: `StrandsAgentsChatbot-${this.stackName}`,
      description: "Strands Agents Chatbot for intelligent IoT device management and monitoring",
      handler: "agent_handler.handler",
      code: lambda.Code.fromAsset(zipApp),

      timeout: Duration.seconds(120),
      memorySize: 512,
      layers: [dependenciesLayer],
      architecture: lambda.Architecture.ARM_64,
    });

    // Add permissions for the Lambda function to invoke Bedrock APIs
    iotAgentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources: [
          "arn:aws:bedrock:*::foundation-model/amazon.nova-pro-v1:0",
          "arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0",
          "arn:aws:bedrock:*::foundation-model/amazon.nova-micro-v1:0",
          "arn:aws:bedrock:*::foundation-model/us.amazon.nova-pro-v1:0",
          "arn:aws:bedrock:*::foundation-model/us.amazon.nova-lite-v1:0",
          "arn:aws:bedrock:*::foundation-model/us.amazon.nova-micro-v1:0",
          "arn:aws:bedrock:*:*:inference-profile/amazon.nova-pro-v1:0",
          "arn:aws:bedrock:*:*:inference-profile/amazon.nova-lite-v1:0",
          "arn:aws:bedrock:*:*:inference-profile/amazon.nova-micro-v1:0",
          "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-pro-v1:0",
          "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-lite-v1:0",
          "arn:aws:bedrock:*:*:inference-profile/us.amazon.nova-micro-v1:0"
        ],
      }),
    );

    // Add IoT permissions for the Lambda function
    iotAgentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "iot:ListThings",
          "iot:ListThingTypes",
          "iot:DescribeThing",
          "iot:GetThingShadow",
          "iot:UpdateThingShadow",
          "iot:SearchIndex"
        ],
        resources: ["*"],
      }),
    );

    // Add Athena permissions for GPS data queries
    iotAgentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution"
        ],
        resources: ["*"],
      }),
    );

    // Add S3 permissions for Athena query results
    iotAgentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        resources: ["*"],
      }),
    );

    // Add Glue permissions for Athena data catalog
    iotAgentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetPartitions"
        ],
        resources: ["*"],
      }),
    );

    // Create API Gateway
    const api = new apigateway.RestApi(this, "AgentApi", {
      restApiName: `IoT-Strands-Agents-Chatbot-API-${this.stackName}`,
      description: "API for IoT device management chatbot powered by Strands Agents",
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"],
      },
    });

    // Create API Key
    const apiKey = new apigateway.ApiKey(this, "AgentApiKey", {
      apiKeyName: `iot-strands-agents-chatbot-key-${this.stackName}`,
      description: "API Key for IoT Strands Agents Chatbot",
    });

    // Create Usage Plan
    const usagePlan = new apigateway.UsagePlan(this, "AgentUsagePlan", {
      name: `iot-strands-agents-chatbot-usage-plan-${this.stackName}`,
      description: "Usage plan for IoT Strands Agents Chatbot API",
      throttle: {
        rateLimit: 100,
        burstLimit: 200,
      },
      quota: {
        limit: 10000,
        period: apigateway.Period.MONTH,
      },
    });

    // Associate API Key with Usage Plan
    usagePlan.addApiKey(apiKey);
    usagePlan.addApiStage({
      stage: api.deploymentStage,
    });

    // Create Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(iotAgentFunction);

    // Create chat resource with API key requirement
    const chatResource = api.root.addResource("chat");
    chatResource.addMethod("POST", lambdaIntegration, {
      apiKeyRequired: true,
    });

    // Output the API URL, API Key, and Lambda Function Name
    new CfnOutput(this, "ApiUrl", {
      value: api.url,
      description: "IoT Strands Agents Chatbot API URL",
    });

    new CfnOutput(this, "ApiKeyId", {
      value: apiKey.keyId,
      description: "API Key ID for IoT Strands Agents Chatbot (use AWS CLI to get the actual key value)",
    });

    new CfnOutput(this, "LambdaFunctionName", {
      value: iotAgentFunction.functionName,
      description: "Lambda Function Name for IoT Strands Agents Chatbot",
    });
  }
}

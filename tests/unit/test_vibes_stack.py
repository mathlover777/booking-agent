import aws_cdk as core
import aws_cdk.assertions as assertions

from vibes.vibes_stack import VibesStack

# example tests. To run these tests, uncomment this file along with the example
# resource in vibes/vibes_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = VibesStack(app, "vibes")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })

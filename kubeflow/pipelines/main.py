import os
import kfp
from kfp import compiler
from kfp import dsl
import auth

KUBEFLOW_ENDPOINT = "https://20.215.85.41"
KUBEFLOW_USERNAME = "user@example.com"
KUBEFLOW_PASSWORD = os.environ.get("KUBEFLOW_PASSWORD")

auth_session = auth.get_istio_auth_session(
    url=KUBEFLOW_ENDPOINT,
    username=KUBEFLOW_USERNAME,
    password=KUBEFLOW_PASSWORD
)

client = kfp.Client(host=f"{KUBEFLOW_ENDPOINT}/pipeline", cookies=auth_session["session_cookie"], verify_ssl=False)



@dsl.component
def print_hello_world():
    print("Hello World!")


@dsl.pipeline(
      name="Test pipeline",
      description="A simple test pipeline to test kubeflow pipelines"
)
def my_pipeline():
  hello_world_task = print_hello_world()


client.create_run_from_pipeline_func(my_pipeline, namespace="kubeflow-user-example-com")

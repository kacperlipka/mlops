import kfp
from kfp import compiler
from kfp import dsl

@dsl.component
def print_hello_world():
    print("Hello World!")

@dsl.pipeline(
      name="Test pipeline",
      description="A simple test pipeline to test kubeflow pipelines"
)
def my_pipeline():
  hello_world_task = print_hello_world()

if __name__ == '__main__':
  compiler.Compiler().compile(my_pipeline, __file__ + '.yaml')
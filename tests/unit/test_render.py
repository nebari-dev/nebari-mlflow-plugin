import os

from src.nebari_plugin_mlflow_chart import MlflowStage

def test_ctor():
    sut = MlflowStage(output_directory = None, config = None)
    assert sut.name == "mlflow"
    assert sut.priority == 102
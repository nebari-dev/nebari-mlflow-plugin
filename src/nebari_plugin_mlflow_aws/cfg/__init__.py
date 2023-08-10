from nebari.schema import Base
from typing import Optional

from nebari_helm_stage import InputSchema as HelmStageInputSchema

class InputSchema(Base):
    mlflow_chart: HelmStageInputSchema = HelmStageInputSchema()
    
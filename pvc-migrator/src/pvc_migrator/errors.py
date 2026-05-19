from __future__ import annotations


class PvcMigratorError(Exception):
    pass


class RenderChartError(PvcMigratorError):
    pass


class ClusterInspectionError(PvcMigratorError):
    pass


class PlanValidationError(PvcMigratorError):
    pass


class ExecutionBlockedError(PvcMigratorError):
    pass

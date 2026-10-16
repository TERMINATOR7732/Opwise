"""Translation from Google OR-Tools CP-SAT status codes to honest domain ScheduleStatus.

Governed by SOLVER_MODEL.md Section 5.1 and PROJECT_RULES.md Section 6.1.
"""

from ortools.sat.python import cp_model

from opwise.domain.entities import ScheduleStatus


def map_cp_sat_status(cp_sat_status: int) -> ScheduleStatus:
    """Translate an OR-Tools CP-SAT integer status into an honest domain ScheduleStatus.

    Mapping Rules:
    - OPTIMAL (4) -> ScheduleStatus.OPTIMAL (proven mathematically)
    - FEASIBLE (2) -> ScheduleStatus.FEASIBLE (satisfies all constraints, optimality unproven)
    - INFEASIBLE (3) -> ScheduleStatus.INFEASIBLE (proven mathematical contradiction)
    - MODEL_INVALID (1) -> ScheduleStatus.MODEL_INVALID (structural modeling defect)
    - UNKNOWN (0) -> ScheduleStatus.TIMEOUT (search terminated before discovering a feasible solution)
    """
    if cp_sat_status == cp_model.OPTIMAL:
        return ScheduleStatus.OPTIMAL
    if cp_sat_status == cp_model.FEASIBLE:
        return ScheduleStatus.FEASIBLE
    if cp_sat_status == cp_model.INFEASIBLE:
        return ScheduleStatus.INFEASIBLE
    if cp_sat_status == cp_model.MODEL_INVALID:
        return ScheduleStatus.MODEL_INVALID
    if cp_sat_status == cp_model.UNKNOWN:
        return ScheduleStatus.TIMEOUT

    return ScheduleStatus.MODEL_INVALID

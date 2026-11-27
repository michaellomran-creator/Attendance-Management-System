from typing import Dict, List

ALL_PERMISSIONS: List[tuple[str, str, str]] = [
    # Platform
    ("platform:manage_orgs", "Manage Organizations", "platform"),
    ("platform:view_analytics", "View Platform Analytics", "platform"),
    ("platform:manage_settings", "Manage Platform Settings", "platform"),
    ("platform:view_audit", "View Platform Audit Logs", "platform"),
    # Organization
    ("org:manage_settings", "Manage Organization Settings", "organization"),
    ("org:manage_users", "Manage Organization Users & Roles", "organization"),
    ("org:manage_terminals", "Manage Attendance Terminals", "organization"),
    ("org:view_audit", "View Organization Audit Logs", "organization"),
    # Structure
    ("dept:manage", "Manage Departments", "structure"),
    ("dept:view", "View Departments", "structure"),
    ("location:manage", "Manage Locations", "structure"),
    ("position:manage", "Manage Positions", "structure"),
    # Employees
    ("employee:create", "Create Employees", "employees"),
    ("employee:read", "View Employees", "employees"),
    ("employee:update", "Update Employees", "employees"),
    ("employee:deactivate", "Deactivate Employees", "employees"),
    ("employee:import", "Bulk Import Employees", "employees"),
    # Shifts
    ("shift:manage", "Manage Shifts & Policies", "shifts"),
    ("shift:assign", "Assign Shifts", "shifts"),
    ("shift:view", "View Shifts", "shifts"),
    # Attendance
    ("attendance:view_all", "View All Organization Attendance", "attendance"),
    ("attendance:view_department", "View Department Attendance", "attendance"),
    ("attendance:view_own", "View Own Attendance", "attendance"),
    ("attendance:record_own", "Record Own Attendance", "attendance"),
    ("attendance:correct_approve", "Approve Attendance Corrections", "attendance"),
    ("attendance:correct_request", "Submit Attendance Corrections", "attendance"),
    # Leave
    ("leave:approve", "Approve/Reject Leave Requests", "leave"),
    ("leave:request", "Submit Leave Requests", "leave"),
    ("leave:view_all", "View All Leave Requests", "leave"),
    ("leave:view_department", "View Department Leave Requests", "leave"),
    ("leave:manage_types", "Manage Leave Types", "leave"),
    # Reports
    ("report:view", "View Attendance Reports", "reports"),
    ("report:export", "Export Attendance Reports", "reports"),
]

ROLE_PERMISSION_MAP: Dict[str, List[str]] = {
    "platform_owner": [p[0] for p in ALL_PERMISSIONS if p[2] == "platform"],
    "org_admin": [p[0] for p in ALL_PERMISSIONS if p[2] != "platform"],
    "hr_manager": [
        "dept:view",
        "employee:create",
        "employee:read",
        "employee:update",
        "employee:deactivate",
        "employee:import",
        "shift:view",
        "shift:assign",
        "attendance:view_all",
        "attendance:correct_approve",
        "leave:view_all",
        "leave:approve",
        "leave:manage_types",
        "report:view",
        "report:export",
    ],
    "department_manager": [
        "dept:view",
        "employee:read",
        "shift:view",
        "attendance:view_department",
        "attendance:correct_approve",
        "leave:view_department",
        "leave:approve",
        "report:view",
        "report:export",
    ],
    "employee": [
        "attendance:view_own",
        "attendance:record_own",
        "shift:view",
        "leave:request",
        "attendance:correct_request",
    ],
}

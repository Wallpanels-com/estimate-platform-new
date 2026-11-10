import type { StaffMember, StaffStatus } from "./staff";

// Keep the HR department navigation and chart in the headcount register order.
const departmentOrder = [
  "Founders", "Management", "Sales", "Design", "Drawings (draftsmen)",
  "Projects & procurement", "Production", "Installation", "Marketing",
  "HR", "Accounting", "Partners",
];

export function compareStaffDepartments(a: string, b: string) {
  const rank = (name: string) => {
    const index = departmentOrder.indexOf(name);
    return index < 0 ? departmentOrder.length : index;
  };
  return rank(a) - rank(b) || a.localeCompare(b);
}

export function staffDepartments(people: StaffMember[], status: StaffStatus | "") {
  return [...new Set(people
    .filter((person) => !status || person.status === status)
    .map((person) => person.department)
    .filter(Boolean))].sort(compareStaffDepartments);
}

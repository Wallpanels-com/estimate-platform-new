import type { StaffMember } from "./staff";
import { compareStaffDepartments } from "./staffDepartments";

export const isStaffFounder = (person: StaffMember) =>
  person.department.trim().toLowerCase() === "founders";

/** Build local department trees. Cross-department managers are labels, never
 * long wires across unrelated teams. Missing managers and cycles keep every
 * person visible exactly once; no source reporting relationships are changed. */
export function staffHierarchy(people: StaffMember[]) {
  const founders = people.filter(isStaffFounder);
  const names = [
    ...new Set(
      people.filter((p) => !isStaffFounder(p)).map((p) => p.department),
    ),
  ].sort(compareStaffDepartments);
  const departments = names.map((name) => {
    const members = people.filter(
      (p) => !isStaffFounder(p) && p.department === name,
    );
    const byId = new Map(members.map((p) => [p.id, p]));
    const children = new Map<string, StaffMember[]>();
    const roots: StaffMember[] = [];
    for (const person of members) {
      let ancestor = person.manager_id;
      const seen = new Set([person.id]);
      let cycle = false;
      while (ancestor && byId.has(ancestor)) {
        if (seen.has(ancestor)) {
          cycle = true;
          break;
        }
        seen.add(ancestor);
        ancestor = byId.get(ancestor)!.manager_id;
      }
      if (!cycle && person.manager_id && byId.has(person.manager_id)) {
        const siblings = children.get(person.manager_id) || [];
        siblings.push(person);
        children.set(person.manager_id, siblings);
      } else roots.push(person);
    }
    return { name, members, roots, children };
  });
  return { founders, departments };
}

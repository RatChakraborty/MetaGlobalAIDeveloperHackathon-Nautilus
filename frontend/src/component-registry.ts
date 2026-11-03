// Registry of research-vehicle components shown in inspection views.
// Each component names the evidence record it is grounded in. Evidence refs must resolve
// against the refs present in the loaded record; components never invent sensor data.
export type ComponentId = 'hull' | 'thrusters' | 'lamp' | 'cable' | 'sensor_head' | 'skid' | 'frame';

export type ComponentEntry = {
  id: ComponentId;
  label: string;
  description: string;
  evidence_refs: string[];
  inspection_modes: string[];
};

export const COMPONENT_REGISTRY: ComponentEntry[] = [
  {id: 'hull', label: 'Pressure hull', description: 'Yellow capsule hull carrying the controller and ballast.', evidence_refs: [], inspection_modes: ['bow', 'stern', 'port', 'starboard', 'three-quarter']},
  {id: 'thrusters', label: 'Thrusters', description: 'Two rotors producing the commanded longitudinal thrust.', evidence_refs: [], inspection_modes: ['stern', 'underside', 'close']},
  {id: 'lamp', label: 'Forward lamp', description: 'Forward light used for visual inspection.', evidence_refs: [], inspection_modes: ['bow', 'close']},
  {id: 'cable', label: 'Tether', description: 'Umbilical cable linking the vehicle to the surface.', evidence_refs: [], inspection_modes: ['top', 'three-quarter']},
  {id: 'sensor_head', label: 'Sensor head', description: 'Forward sensor dome.', evidence_refs: [], inspection_modes: ['bow', 'close']},
  {id: 'skid', label: 'Ground skid', description: 'Lower skid frame and ballast rails.', evidence_refs: [], inspection_modes: ['underside']},
  {id: 'frame', label: 'Frame', description: 'Structural frame connecting thrusters and skids.', evidence_refs: [], inspection_modes: ['underside', 'port', 'starboard']},
];

// Returns the components a view should show, and rejects references that the record does not contain.
export function componentsForMode(mode: string, recordRefs: Set<string>): ComponentEntry[] {
  for (const c of COMPONENT_REGISTRY) {
    if (c.evidence_refs.some(ref => !recordRefs.has(ref))) throw Error(`Component ${c.id} references unknown evidence`);
  }
  return COMPONENT_REGISTRY.filter(c => c.inspection_modes.includes(mode));
}

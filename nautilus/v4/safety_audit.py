"""Read-only public-ensemble audit. No hidden development-case truth is exported."""
from dataclasses import replace
from ..lab_safety import uncertainty_cases,guarded_trial,PREDICTIVE_LIMIT
from ..v2_experiments import Trial
from ..simulator import Vehicle


def run():
    trials=(('zero_commands',Trial('thrust_step',duration_s=4.,amplitude_n=0.,phase_s=2.)),
            ('feedback_no_diagnostic_target',Trial('heading_response',duration_s=4.,cruise_thrust_n=0.,phase_s=2.,heading_step_rad=0.)),
            ('small_diagnostic',Trial('differential_step',duration_s=4.,cruise_thrust_n=2.,differential_n=.5,phase_s=2.)))
    result=[]
    for index,(faults,plant,controller) in enumerate(uncertainty_cases()):
        for label,trial in trials:
            for ablation in ('original','without_current','without_lag','without_deadzone'):
                f=replace(faults,current_y=0.) if ablation=='without_current' else faults
                p=replace(plant,actuator_tau_s=0.) if ablation=='without_lag' else replace(plant,thrust_deadzone_n=0.) if ablation=='without_deadzone' else plant
                rows,meta,_=guarded_trial(trial,f,p,controller,0,noise_y=0.)
                guard=meta['guard_time_s'];after=[r['observed_y_m'] for r in rows if guard is not None and r['time_s']>=guard]
                magnitude=max(max(abs(r['port_command_n']),abs(r['starboard_command_n'])) for r in rows)
                maximum=max(abs(r['observed_y_m']) for r in rows)
                result.append({'stress_case':index,'condition':label,'ablation':ablation,'observed_max_y_m':maximum,'predictive_margin_m':PREDICTIVE_LIMIT-maximum-.14,'max_command_n':magnitude,'saturated_samples':sum(max(abs(r['port_command_n']),abs(r['starboard_command_n']))>=Vehicle().max_thrust-1e-9 for r in rows),'above_25n_parameter_envelope_samples':sum(max(abs(r['port_command_n']),abs(r['starboard_command_n']))>25. for r in rows),'physical_command_clip_n':Vehicle().max_thrust,'guard_intervened':meta['guard_intervened'],'guard_time_s':guard,'post_guard_observed_delta_m':after[-1]-after[0] if after else None,'observed_excursion':meta['observed_excursion'],'containment':'unverified'})
    return {'schema_version':'nautilus.safety-audit.v4','rows':result,'qualification':'Fixed public stress ensemble; one-factor ablations are not additive causal contributions. Commands zero is a genuine no-excitation condition. Feedback target zero can still generate thrust. No private case truth. No global infeasibility proof or controller change.'}

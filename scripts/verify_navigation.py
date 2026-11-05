"""Reproduce source checks and an explicitly assumed local-frame preview."""
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
from pathlib import Path

SOURCE = 'https://github.com/nature1949/AUV_navigation_dataset/blob/main/20220712_0_1.csv'
SOURCE_SHA = '3287424eafd36f5e3129ad9bd2c21c827fc9779338f4136e84b2a6ea6369973c'


def verify(data):
    matches = hashlib.sha256(data).hexdigest() == SOURCE_SHA
    rows = list(csv.DictReader(io.StringIO(data.decode())))
    invalid = []
    valid = []
    for i, row in enumerate(rows):
        try:
            values = {k:float(v) for k,v in row.items()}
            if any(not math.isfinite(v) for v in values.values()) or not -90 <= values['lat'] <= 90 or not -180 <= values['lon'] <= 180:
                raise ValueError('Nonfinite or invalid geographic value')
            valid.append((i, values))
        except (ValueError, TypeError):
            invalid.append(i)
    if len(valid) < 2:
        raise ValueError('At least two valid navigation samples required')
    intervals = [b[1]['time']-a[1]['time'] for a,b in zip(valid,valid[1:])]
    origin = valid[0][1]
    selected = [(i,r) for i,r in valid if origin['time'] <= r['time'] <= origin['time']+20]
    preview = []
    stride = max(1,len(selected)//16)
    for i,r in selected[::stride]:
        preview.append({'source_row':i,'time_s_assumed':r['time'], 'measured_lat':r['lat'], 'measured_lon':r['lon'],
                        'east_m_assumed':6378137.*math.cos(math.radians(origin['lat']))*math.radians(r['lon']-origin['lon']),
                        'north_m_assumed':6378137.*math.radians(r['lat']-origin['lat'])})
    return {'schema_version':'nautilus.field-verification.v1','source':SOURCE if matches else 'Unverified input; reviewed source hash did not match',
            'source_sha256':hashlib.sha256(data).hexdigest(),'matches_reviewed_source':matches,
            'license':{'name':'CC0-1.0' if matches else 'unverified','source':'https://github.com/nature1949/AUV_navigation_dataset/blob/main/LICENSE'},
            'reference':'https://www.mdpi.com/2079-9292/12/18/3788',
            'rows':len(rows),'valid_rows':len(valid),'excluded_rows':invalid,
            'time':{'first':valid[0][1]['time'],'last':valid[-1][1]['time'],'strictly_increasing':all(d>0 for d in intervals),
                    'interval_min':min(intervals),'interval_median':statistics.median(intervals),'interval_max':max(intervals)},
            'checks':{'geographic_ranges':'Passed','finite_values':'Passed' if not invalid else 'Failed',
                      'timestamp_monotonicity':'Passed' if all(d>0 for d in intervals) else 'Failed',
                      'source_license':'Passed' if matches else 'Not verified','heading_convention':'Not verified','velocity_frame':'Not verified',
                      'physical_units':'Not independently reverified from original workbook in this environment'},
            'transformation':{'classification':'TRANSFORMED / ASSUMED','method':'Local tangent-plane equirectangular approximation, R=6378137 m; east=R*cos(lat0)*delta_lon, north=R*delta_lat; angular deltas converted from assumed degrees.',
                              'origin':{'lat':origin['lat'],'lon':origin['lon']},'selected_rows':len(selected),
                              'selected_interval':[selected[0][1]['time'],selected[-1][1]['time']],
                              'height':'Not used; no depth inferred.','preview':preview},
            'compatibility':{'decision':'withheld','bridge_executed':False,
                             'reason':'Original heading/velocity conventions and full units documentation could not be independently retrieved here. No thruster commands or physical fault labels are supplied; a matched dynamic bridge is not established.'},
            'limitations':['The navigation observations are real. Fault and controller evaluations elsewhere in Nautilus are simulated. No controller revision was validated on the original physical vehicle.',
                           'No velocity-to-thrust conversion, current estimate, fault diagnosis or physical controller evaluation is inferred from this CSV.',
                           'The coordinate preview assumes latitude/longitude degrees and a short local tangent plane; heading and velocity are intentionally not transformed.']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=verify(args.source.read_bytes())
    if not result['matches_reviewed_source']:
        raise ValueError('Input does not match the reviewed public source; no attributed record written')
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')

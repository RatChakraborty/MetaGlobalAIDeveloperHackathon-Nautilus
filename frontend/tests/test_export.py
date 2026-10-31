import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('export',Path(__file__).parents[1]/'export_records.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ExportTests(unittest.TestCase):
    def rows(self):return [{k:(i*.05 if k=='time_s' else 0.) for k in module.FIELDS} for i in range(3)]
    def record(self,extra=None):
        body={'index':0,'type':'observation','previous_hash':None,'observations':self.rows(),**(extra or {})}
        return {'record':{'after':{'history':[{**body,'event_hash':module.digest(body)}]},'private_execution':[{'truth':'DO_NOT_EXPORT'}]},'private_faults':{'secret':3.}}
    def test_allowlist_excludes_private_source_siblings(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'record.json';p.write_text(json.dumps(self.record()));result=module.public_record(p)
            self.assertNotIn('DO_NOT_EXPORT',json.dumps(result));self.assertNotIn('private_faults',json.dumps(result));self.assertEqual(len(result['ledger']),1)
    def test_tamper_private_keys_and_extra_channels_rejected(self):
        for change in ('hash','private','channel'):
            with tempfile.TemporaryDirectory() as d:
                data=self.record();event=data['record']['after']['history'][0]
                if change=='hash':event['event_hash']='bad'
                if change=='private':event['truth']=[1]
                if change=='channel':event['observations'][0]['x_m']=1
                p=Path(d)/'record.json';p.write_text(json.dumps(data))
                with self.assertRaises(ValueError):module.public_record(p)
    def test_output_cannot_enter_source_tree(self):
        with self.assertRaises(ValueError):module.write(Path(__file__).parents[1]/'public'/'investigation.json',{})
    def test_visual_reference_is_allowlisted_and_samples_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);observed=root/'observed.csv';truth=root/'truth.csv'
            observed.write_text('time_s\n0\n1\n');truth.write_text('time_s,x_m,y_m,heading_rad\n0,2,3,0.1\n1,4,-1,-0.2\n')
            (root/'run.json').write_text(json.dumps({'mission':{'cable_length_m':110,'cable_half_width_m':1.5,'seed':999},'private_faults':{'secret':3}}))
            result=module.visualization(truth,observed,'test')
            self.assertEqual(set(result['reference']),{'cable_length_m','cable_half_width_m','source'})
            self.assertEqual(result['samples'][1],{'time_s':1.,'x_m':4.,'y_m':-1.,'heading_rad':-.2})
            self.assertNotIn('secret',json.dumps(result));self.assertNotIn('seed',json.dumps(result))

    def test_missing_visual_coordinates_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'truth.csv';p.write_text('time_s,y_m\n0,0\n1,1\n')
            with self.assertRaises(KeyError):module.visualization(p,p,'test')

if __name__=='__main__':unittest.main()

"""Local test data from existing numerical/export test infrastructure. Not a demo dataset."""
import importlib.util,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from test_host_evaluation import laboratory,scenario,response,ConfigurationEvaluationHost,Controller
from v4_fixture import fixture as v4_fixture

def fixture():
    spec=importlib.util.spec_from_file_location('test_exporter',Path('frontend/export_records.py'));export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);lab=laboratory();result=ConfigurationEvaluationHost(scenario(),Controller(),authorized=True).finish(lab,response(lab))
        source=p/'source.json';source.write_text(json.dumps({'history':lab.ledger}));out=p/'exports';export.export_host_evaluation(result,source,out)
        files={file.name:file.read_text() for file in out.glob('*.json')}
    return {'files':files,'v4':v4_fixture()}

if __name__=='__main__':print(json.dumps(fixture()))

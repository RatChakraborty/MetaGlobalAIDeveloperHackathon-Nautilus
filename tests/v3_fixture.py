"""Offline cross-language fixture; genuine laboratory with fake model replies."""
from test_muse_v3 import laboratory,critic,Fake,call_reply,proposal
from nautilus.muse_v3 import Flags,run
from nautilus.controller_context import canonical
import json

def fixture():
    flags=Flags(False,False,True,False);lab=laboratory(flags)
    cp=critic(lab);original=cp.fn
    def unicode_reply(i,k):
        from dataclasses import replace
        r=original(i,k);v=json.loads(r.output[0]['content'][0]['text']);v['rationale']='Model judgment — not independently verified.'
        return replace(r,output=[{'type':'message','content':[{'type':'output_text','text':canonical(v)}]}])
    cp.fn=unicode_reply
    def step(i,k):
        if i==1:return call_reply(i,'finalize',proposal(lab))
        result=json.loads(k['input'][0]['output'])['result']
        return call_reply(i,'finalize',proposal(lab,result['required_response_marker']+' I retain abstention because competing explanations and missing channels remain unresolved.'))
    return run(lab,Fake(step),critic_provider=cp,flags=flags)

if __name__=='__main__':print(canonical(fixture()))

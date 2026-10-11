"""Evaluate a user-supplied native-model reply without any provider or app write.

Usage: python scripts/review_manual_decision.py packet.json reply.json output.json
The output is a new immutable evidence artifact, never a production fixture.
"""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.decisions import validate_decision,decision_record,offline_decision
from backend.app.domain import digest

context=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert context['packet_id']==digest({k:v for k,v in context.items() if k!='packet_id'}),'Packet content hash mismatch'
reply=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
value=validate_decision(context,reply)
result={'record':decision_record(context,value,'manual_native_model'),
        'offline_comparator':offline_decision(context),'provider_calls':0,
        'production_actions':0,'billing_and_latency':'not measured',
        'note':'Human-mediated native chat reasoning. No live API or autonomous runtime integration claim.'}
with Path(sys.argv[3]).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))

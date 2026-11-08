"""Read native simultaneous Newton forces; never starts an FE solve or accepts a sample."""
import argparse,json,re,shutil,subprocess,sys,tarfile
from pathlib import Path
import httpx,numpy as np
from native_cloud_worker import native_runtime
from campaign_checkpoint_transport import ReleaseAssetTransport,restore_checkpoint
from honeycomb_studio import solver
from honeycomb_studio.campaign import one_run_spec
from honeycomb_studio.campaign_queue import ticket_key
from honeycomb_studio.cloud_github import Catalog,Github
from honeycomb_studio.data import checksum
from honeycomb_studio.models import BatchSpec,expand,digest
from honeycomb_studio.store import write_json
ROOT=Path('/tmp/honeycomb-force-probe')
def field_acceleration_requested(deck):
 mode=None;node_output=False
 for raw in deck.splitlines():
  line=raw.strip().upper()
  if not line or line.startswith('**'):continue
  if line.startswith('*OUTPUT'):
   mode='field' if re.search(r'\bFIELD\b',line) else 'history'
   node_output=False
  elif line.startswith('*'):
   node_output=line.split(',')[0]=='*NODE OUTPUT'
  elif mode=='field' and node_output and 'A' in [x.strip() for x in line.split(',')]:
   return True
 return False

def main():
 import os
 parser=argparse.ArgumentParser();parser.add_argument('--ticket',required=True);parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
 github=Github(token=os.environ['GITHUB_TOKEN']);work,_=Catalog(github).get(ticket_key('core-damage-v2-20261107-v6p5',args.ticket))
 assert work['archive_verified'] and work['archive']['complete'] and work['outcome']=='completed'
 archive=work['archive'];metadata=[f for f in archive['files'] if f['path'].endswith(('/run.json','.inp')) and '/bounded-extraction-' not in f['path']]
 ROOT.mkdir(exist_ok=True)
 with httpx.Client(timeout=120,follow_redirects=True) as body:
  restore_checkpoint({**archive,'files':metadata},ROOT,transport=ReleaseAssetTransport(github,body))
 run=json.loads(next(ROOT.rglob('run.json')).read_text());expected=expand(BatchSpec.model_validate(one_run_spec(work['design'])))[0]
 assert run['resolved']==expected['resolved'] and run['input_hash']==expected['input_hash'] and digest(run['resolved'])==work['design']['physics_hash']
 deck=next(ROOT.rglob('*.inp'));available=field_acceleration_requested(deck.read_text())
 if args.preflight:
  with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('native_required='+str(available).lower()+'\n')
 if not available:
  result=dict(ticket=args.ticket,passed=False,simultaneous_acceleration_available=False,
   reason='Original INP does not request field A; history A3 cannot prove simultaneous acceleration at an off-grid field frame',
   original_inp_sha256=checksum(deck),original_physics_hash=work['design']['physics_hash'],
   new_fe_processes=0,numerical_gate_changed=False,odb_downloaded=False)
  write_json(Path('output/force-sampling-probe.json'),result);print(json.dumps(result,indent=2),flush=True);return
 if args.preflight:return
 files=[f for f in archive['files'] if f['path']=='field-reductions.tar' or f['path'].endswith(('/extracted/histories.json','.odb')) and '/bounded-extraction-' not in f['path']]
 with httpx.Client(timeout=120,follow_redirects=True) as body:
  restore_checkpoint({**archive,'files':files},ROOT,transport=ReleaseAssetTransport(github,body))
 histories=json.loads(next(ROOT.rglob('histories.json')).read_text());h=next(h for h in histories if h['variable']=='A3' and 'IMPACTOR' in h['region'].upper())
 region=re.fullmatch(r'Node (IMPACTOR-[0-9]+)\.([0-9]+)',h['region'].upper());assert region,'Unexpected reference history identity'
 times=np.array([x[0] for x in h['data']]);forces=run['resolved']['impact_mass']*(np.array([x[1] for x in h['data']])+run['resolved']['gravity']*1000.)
 checks={}
 with tarfile.open(ROOT/'field-reductions.tar') as tar:
  for member in tar:
   if not member.isfile() or '/extracted/reduced-fields/' not in member.name or not member.name.endswith('.json'):continue
   row=json.load(tar.extractfile(member))
   if 'impactor_force_z_N' not in row:continue
   key=(row['step'],row['frame'],row['time_s']);checks[key]=checks.get(key,0)+row['impactor_force_z_N']
 # Every off-grid field frame is audited; no frame is discarded from the check.
 frames=[dict(step=s,frame=f,time_s=t,exported_contact_force_N=x,interpolated_inertial_force_N=float(np.interp(t,times,forces))) for (s,f,t),x in checks.items() if float(np.min(abs(times-t)))>1.e-10]
 assert frames,'No off-grid frame was exercised'
 odb=next(ROOT.rglob('*.odb'));before=checksum(odb)
 reader=ROOT/'frame_inertia.py';shutil.copyfile('src/honeycomb_studio/adapters/frame_inertia.py',reader)
 config=ROOT/'config.json';destination=ROOT/'exact-frame-inertia.json'
 write_json(config,dict(odb=str(odb),destination=str(destination),frames=frames,instance=region.group(1),node_label=int(region.group(2)),impact_mass=run['resolved']['impact_mass'],gravity=run['resolved']['gravity']))
 with native_runtime(ROOT,continuation=True) as executable:
  with (ROOT/'native-read.log').open('w') as log:
   subprocess.run(solver.command(str(executable),'python',str(reader),str(config)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
 assert checksum(odb)==before
 result=json.loads(destination.read_text());result.update(ticket=args.ticket,original_odb_sha256=before,original_physics_hash=work['design']['physics_hash'],source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),new_fe_processes=0,peak_history_force_N=float(max(forces)))
 for row in result['rows']:
  row['simultaneous_relative_percent']=100*abs(row['contact_force_N']-row['inertial_force_N'])/max(forces)
  row['field_export_relative_percent']=100*abs(row['contact_force_N']-row['exported_contact_force_N'])/max(forces)
 result['passed']=all(r['simultaneous_relative_percent']<=2 and r['field_export_relative_percent']<.001 for r in result['rows'])
 write_json(Path('output/force-sampling-probe.json'),result);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()

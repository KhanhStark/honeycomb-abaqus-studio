import json
from pathlib import Path
import pytest
from honeycomb_studio.cloud_continuation import checkpoint_stop_time, verify_checkpoint_history

HEADER = 'Abaqus/Explicit 2020 DATE 08-Nov-2026 TIME 10:00:00\n'
def native_stop(increment, time, *, stable=1e-8):
 return (f'***WARNING: An additional restart frame at the end of increment {increment} is\n'
   ' requested in VEXTERNALDB.\n'
   '***ERROR: The program will exit as per user request in VEXTERNALDB.\n'
   f' {increment} {time:.3E} {time:.3E} 01:00:00 {stable:.3E} 1 1.0E+00 1.0E+00\n'
   f'Restart Number 1 at {time:.5E}\n'
   '***ERROR: The fatal error will generate a new field output in the last\n'
   f' {increment+1} {time:.3E} {time:.3E} 01:00:00 1.000E-14 1 1.0E+00 1.0E+00\n'
   'A special ODB Field Frame with all relevant variables was written\n'
   'THE ANALYSIS HAS NOT BEEN COMPLETED\n')

def recovered(tmp_path):
 ack={'simulation_time_s':.0018821095873614207,'increment':402432}
 pred={'stop':{'simulation_time_s':.004962079179169679,'increment':247552},'history_integrity':{'passed':True}}
 text=HEADER+native_stop(247552,.00496210,stable=2e-8)+HEADER+native_stop(402432,.00684421,stable=1.291e-8)
 (tmp_path/'hc.sta').write_text(text)
 return ack,pred,text

def test_recovered_callback_time_is_not_the_absolute_odb_time(tmp_path):
 ack,pred,_=recovered(tmp_path)
 stop=checkpoint_stop_time(tmp_path,'hc',ack,pred)
 assert stop['simulation_time_s']==.00684421
 assert stop['predecessor_offset_s']==.00496210
 assert stop['callback_acknowledgment']==ack
 assert ack['simulation_time_s']==.0018821095873614207

@pytest.mark.parametrize('corruption',['no_predecessor','wrong_offset','wrong_increment','native_error','missing_shutdown','missing_restart'])
def test_recovered_time_requires_all_independent_native_evidence(tmp_path,corruption):
 ack,pred,text=recovered(tmp_path)
 if corruption=='no_predecessor':pred=None
 if corruption=='wrong_offset':pred['stop']['simulation_time_s']=.003
 if corruption=='wrong_increment':ack['increment']-=256
 if corruption=='native_error':text+='***ERROR: Excessive distortion\n'
 if corruption=='missing_shutdown':text=text.rsplit('A special ODB Field Frame',1)[0]
 if corruption=='missing_restart':text=text.replace('Restart Number 1 at 6.84421E-03','')
 (tmp_path/'hc.sta').write_text(text)
 with pytest.raises(ValueError):checkpoint_stop_time(tmp_path,'hc',ack,pred)

@pytest.mark.parametrize('gap',[False,True])
def test_recovered_odb_history_keeps_original_gap_and_endpoint_gates(tmp_path,monkeypatch,gap):
 ack,pred,_=recovered(tmp_path)
 (tmp_path/'continuation-stop-ack.json').write_text(json.dumps(ack))
 h=[{'step':'Impact','region':'Assembly','variable':'ALLKE','data':[[i*2e-6,1.] for i in range(3423) if not gap or not 1200<i<1220]}]
 def reader(args,**kwargs):Path(args[-1]).write_text(json.dumps(h))
 monkeypatch.setattr('honeycomb_studio.cloud_continuation.subprocess.run',reader)
 if gap:
  with pytest.raises(ValueError,match='missing original history'):
   verify_checkpoint_history(tmp_path,'hc','abaqus',{'duration':.008,'history_intervals':4000},predecessor=pred)
 else:
  result=verify_checkpoint_history(tmp_path,'hc','abaqus',{'duration':.008,'history_intervals':4000},predecessor=pred)
  assert result['history_integrity']['passed']
  assert result['history_integrity']['maximum_allowed_gap_s']==3e-6

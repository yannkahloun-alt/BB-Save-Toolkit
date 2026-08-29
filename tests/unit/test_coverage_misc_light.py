import json
import pytest
import bbtool.app.console as console
import bbtool.app.main as appmain
import bbtool.app.output as out
import bbtool.html_report as hr
from bbtool.formatting import component_summary

pytestmark=pytest.mark.unit


def test_console_step_and_profile_and_status(capsys, monkeypatch):
    assert callable(appmain.main)
    monkeypatch.setattr(console.time,'perf_counter',lambda:1.0)
    with console.Step('X') as step:
        step.started=0.5
    status={
        'initial_cache':{'dictionary':{'exists':False},'backgrounds':{'exists':True},'perks':{'exists':False}},
        'scripts_download_stats':{'archive_bytes':1048576,'seconds':.1,'members':1,'nut_files':1,'item_scripts':1,'background_scripts':1},
        'dictionary_stats':{'dictionary_ids':2,'output_bytes':1024,'equipment_like':3,'with_value':2,'unresolved':1,'coverage_pct':66.7,
            'exact_hash_matches':2,'exact_hash_with_value':2,'source_value_resolved':2,'source_scripts':3,'source_value_local':2,'source_value_inherited':0,
            'source_value_unresolved':1,'bbedit_download_seconds':.1,'source_parse_seconds':.2,'join_seconds':.01,'write_seconds':.02,'unresolved_sample':['A']},
        'background_stats':{'backgrounds':2,'usable_background_scripts':2,'unusable_background_scripts':1,
            'scripts':{'scanned':3,'decoded':3,'decode_failed':0,'resolution_failed':0},
            'economy_fields':{'hiring_cost':{'local':1,'inherited':1,'unresolved':1},'daily_cost':{'local':1,'inherited':1,'unresolved':1}},
            'identifiers':{'explicit':2,'inferred':1},'parse_seconds':.1},
        'perk_stats':{'perks':3,'stat_modifying':2,'exact_stat_modifying':1,'conditional_stat_modifying':1,'parse_seconds':.1,'output_bytes':1024},
    }
    console.print_reference_status(status)
    console.print_projection_profile({'project_role_calls':3})
    text=capsys.readouterr().out
    assert '[DONE ] X' in text and 'dictionary=no' in text and 'projection calls' in text


def test_console_step_exception_branch(monkeypatch):
    s=console.Step('X'); s.started=0
    assert s.__exit__(ValueError,ValueError('x'),None) is False


def test_output_workspace_raw_analysis_and_archive(tmp_path,bro_factory,monkeypatch):
    save=tmp_path/'s.sav'; save.write_bytes(b'abc')
    ws=out.create_workspace(save,tmp_path/'out')
    b=bro_factory(FutureRolls={'MAtk':[3]})
    out.write_raw_inputs(ws,[b],[{'Name':'R'}])
    roster=json.loads((ws.root/f'{ws.base}-roster.json').read_text(encoding='utf-8'))
    assert 'FutureRolls' not in roster[0]
    fits=[{'ProjectedComponents':{'MAtk':{'value':70,'weight':2,'utility':0.8}},'ProjectedRanges':{'MAtk':{'min':1,'max':3,'ev':2}}}]
    out.write_analysis_json(ws,fits,[{'Name':'B'}])
    assert 'MAtk:' in fits[0]['ProjectedRangeSummary']
    # archive includes files but not itself
    archive=out.archive_workspace(ws,tmp_path/'out')
    assert archive.exists()


def test_html_small_helpers_and_recruits(bro_factory,monkeypatch):
    assert hr.public_value(None)=='—' and hr.public_value('x')=='x'
    assert hr.bro_anchor('A B').startswith('bro-')
    assert hr.heat(95).startswith('h')
    assert hr.range_text({'min':1,'max':3,'ev':2})
    role={'stats':{'MAtk':{'fit':True,'target':90}}}
    assert 'MAtk' in hr.role_important_stats(role)
    monkeypatch.setattr(hr,'_DESCRIPTION_CACHE',{'Fast':'desc'})
    assert 'title=' in hr.described_items(['Fast'])
    assert hr.described_items([])=='—'
    b=bro_factory(Perks=['Fast'],Traits=['Brave'],Injuries=[])
    chips=hr.current_stat_chips(b,{'HP':70},{'MAtk'})
    assert 'effective-stat' in chips and 'important' in chips
    recruits=[
        {'Settlement':'Town','Name':'A','Title':'T','Level':1,'Background':'B','TryoutDone':True,'Traits':['Fast'],'HireCost':100,'DailyWage':10},
        {'Settlement':'Town','Name':'B','TryoutDone':False,'Traits':[]},
        {'Settlement':'Other','Name':'C','TryoutDone':None,'Traits':[]},
    ]
    rows=hr.recruit_table_rows(recruits)
    panels=hr.recruit_settlement_panels(recruits)
    assert 'traits-revealed' in rows and 'traits-hidden' in rows and 'traits-unknown' in rows
    assert panels.count('settlement-panel')>=2
    assert component_summary({'MAtk':{'value':70,'weight':2,'utility':0.8}})

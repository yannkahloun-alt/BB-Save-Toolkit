import pytest
pytestmark=pytest.mark.unit
from bbtool.html_report import levelup_advice_html,levelup_bro_panel

def advice():
    meta={s:{'Roll':2,'Min':1,'Max':3,'Average':2,'Label':'AVG','Quality':.5} for s in ['HP','Fatigue','Resolve','Initiative','MAtk','RAtk','MDef','RDef']}
    cand={'Stats':['HP','MAtk','MDef'],'Rolls':{'HP':2,'MAtk':2,'MDef':2},'AnchorFitBeforePct':70,'AnchorFitAfterPct':75,'FitMinAfterPct':60,'FitMaxAfterPct':90,'FitLikelyMinAfterPct':65,'FitLikelyMaxAfterPct':85,'FitFeasibilityBeforePct':10,'FitFeasibilityAfterPct':20}
    return {'AnchorRole':'Test','Recommended':cand,'Alternative':None,'PickReasons':{},'AllRolls':meta,'SkippedImportant':[]}
def test_levelup_html_renders_recommendation_and_p5p95():
    h=levelup_advice_html(advice()); assert 'Recommended line' in h and 'HP' in h and 'MAtk' in h and '5th–95th percentile' in h and '10th' not in h
def test_levelup_panel_hidden_without_pending(bro_factory):
    b=bro_factory(); assert levelup_bro_panel(b,{'LevelUpAdvice':None})==''
def test_levelup_panel_uses_summary_advice(bro_factory):
    b=bro_factory(Level=2,LevelPoints=1,CurrentRolls={'HP':2,'MAtk':2,'MDef':2}); s={'LevelUpAdvice':advice(),'BestRole':'Test','ProjectedFitPct':70,'FitFeasibilityPct':10}; h=levelup_bro_panel(b,s); assert 'Recommended line' in h and 'Test' in h
    assert 'data-copy-text="Test 70.0%"' in h

def test_levelup_html_renders_runner_up_rolls_and_anchor():
    a=advice(); alt=dict(a['Recommended']); alt['Stats']=['Fatigue','Resolve','RAtk']; alt['Rolls']={'Fatigue':2,'Resolve':2,'RAtk':2}; alt['AnchorFitAfterPct']=74; alt['Gamble']={'IsGamble':False,'ChanceToBeatPrimaryPct':0,'TiePct':0,'PrimaryWinsPct':0,'MeanDeltaPct':-1,'AvgUpsideWhenWinsPct':0,'MaxUpsidePct':0,'AvgDownsideWhenLosesPct':0,'MaxDownsidePct':0,'Samples':0}; a['Alternative']=alt
    h=levelup_advice_html(a)
    assert 'Alternative line' in h and 'FAT' in h and 'RAtk' in h and a['AnchorRole'] in h

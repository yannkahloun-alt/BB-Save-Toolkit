import inspect
import pytest
pytestmark=pytest.mark.unit
from bbtool.projection.sampling import _radical_inverse, sample_coordinates, sample_dimension
from bbtool.projection.trajectory import _normalize_round_ranges
import bbtool.projection.trajectory as tr
import bbtool.projection.sampling as sampling
@pytest.mark.parametrize('n,b,e',[(0,2,0),(1,2,.5),(2,2,.25),(3,2,.75),(1,3,1/3),(2,3,2/3)])
def test_radical_inverse(n,b,e): assert _radical_inverse(n,b)==pytest.approx(e)
def test_sample_dimension_deterministic_range():
    a=sample_dimension(512,3); b=sample_dimension(512,3); assert a==b and all(0<=x<1 for x in a)
@pytest.mark.parametrize('samples,dims',[(1,1),(512,4),(2048,8)])
def test_coordinates_shape_and_determinism(samples,dims):
    a=sample_coordinates(samples,dims); b=sample_coordinates(samples,dims); assert a==b; assert len(a)==samples; assert all(len(r)==dims for r in a)
def test_no_random_rng_in_projection_sampling_sources():
    src=inspect.getsource(tr)+inspect.getsource(sampling); assert 'import random' not in src and 'np.random' not in src and 'random.' not in src

def test_normalize_partial_and_invalid():
    out=_normalize_round_ranges(2, {'MAtk':(3,3),'BOGUS':(9,9)}, [{'MDef':(1,1)}]); assert out[0]['MAtk']==(3,3); assert out[0]['MDef']==(1,1); assert 'BOGUS' not in out[0]
def test_normalize_zero_rounds(): assert _normalize_round_ranges(0,{'MAtk':(3,3)})==()
def test_normalize_degenerate(): assert _normalize_round_ranges(1,round_ranges=[{'MAtk':(2,2)}])[0]['MAtk']==(2,2)

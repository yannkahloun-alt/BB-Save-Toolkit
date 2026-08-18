import struct, pytest
pytestmark=pytest.mark.unit
from bbtool.save_parser import u16,i16,u32,f32,lp_string,printable_ascii,_squirrel_round

def test_numeric_primitives():
    b=struct.pack('<HhIf',65530,-123,4000000000,1.25); assert u16(b,0)==65530; assert i16(b,2)==-123; assert u32(b,4)==4000000000; assert f32(b,8)==pytest.approx(1.25)
def test_short_buffer_raises():
    for fn in (u16,i16,u32,f32):
        with pytest.raises(struct.error): fn(b'\x00',0)
def test_lp_string_valid():
    raw='Björn'.encode(); b=struct.pack('<H',len(raw))+raw; assert lp_string(b,0)==('Björn',2+len(raw),len(raw))
def test_lp_string_too_long_and_truncated_and_invalid_utf8():
    assert lp_string(struct.pack('<H',999)+b'x',0,max_len=10) is None; assert lp_string(struct.pack('<H',5)+b'ab',0) is None; assert lp_string(struct.pack('<H',1)+b'\xff',0) is None
def test_printable_ascii(): assert printable_ascii('Hello 123'); assert not printable_ascii('Hello\n')
@pytest.mark.parametrize('x,e',[(1.4,1),(1.5,2),(2.5,3),(0.5,1)])
def test_squirrel_round(x,e): assert _squirrel_round(x)==e

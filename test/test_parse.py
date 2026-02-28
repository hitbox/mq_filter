import pytest

from mq_filter.parse import extract_payload_from_mq
from mq_filter.parse import parse_content_for_airline

def check_file(fn, expect_airline):
    with open(fn) as file:
        content = file.read()
        data = parse_content_for_airline(content)
        assert data['airline_code'] == expect_airline

@pytest.mark.parametrize(
    "fn,expect_airline",
    [
        ('test/APIS 8C 1.txt', '8C'),
        ('test/APIS 8C 2.txt', '8C'),
        ('test/APIS Sample 8C 2.txt', '8C'),
        ('test/APIS Sample 8C.txt', '8C'),
        ('test/APIS Sample GB 2.txt', 'GB'),
        ('test/APIS Sample GB.txt', 'GB'),
        ('test/APIS GB.txt', 'GB'),
    ],
)
def test_parse_apis(fn, expect_airline):
    check_file(fn, expect_airline)


@pytest.mark.parametrize(
    "fn,expect_airline",
    [
        ('test/Flight PLan 8C.txt', 'ATN'),
        ('test/Flight Plan GB correct.txt', 'ABX'),
    ],
)
def test_parse_flight_plan(fn, expect_airline):
    check_file(fn, expect_airline)


@pytest.mark.parametrize(
    "fn,expect_airline",
    [
        ('test/MVA ATN.txt', 'ATN'),
        ('test/MVT GB.txt', 'GB'),
    ],
)
def test_parse_mv(fn, expect_airline):
    check_file(fn, expect_airline)


def test_extract_payload():
    message = (
        b"RFH \x00\x00\x00\x02\x00\x00\x01P\x00\x00\x01\x11\x00\x00\x04\xb8MQSTR   "
        b"\x00\x00\x00\x00\x00\x00\x04\xb8\x00\x00\x00 "
        b"<mcd><Msd>jms_text</Msd></mcd>  "
        b"\x00\x00\x00X<jms><Dst>queue:///ISB.STAGSMX.SND.ARINC</Dst>"
        b"<Tms>1770591522997</Tms><Dlv>2</Dlv></jms>"
        b"\x00\x00\x00\xa8<usr><breadcrumbId>125B06B71564E10-0000000000000F4C</breadcrumbId>"
        b"<CamelJmsDeliveryMode dt='i4'>2</CamelJmsDeliveryMode>"
        b"<IOCC_TLX_ID>MRS144594901</IOCC_TLX_ID></usr>   "
        b"\r\n\x01QU ASIKORR\r\n.ATSGOPS 082258\r\n\x02MVA\r\n"
        b"ATN530/08.N751CX.ANU\r\nAD2229/2258 EA0555 ASI\r\n\x03"
    )

    payload = extract_payload_from_mq(message)

    assert payload == (
        '\r\n\x01QU ASIKORR\r\n.ATSGOPS 082258\r\n\x02MVA\r\n'
        'ATN530/08.N751CX.ANU\r\nAD2229/2258 EA0555 ASI\r\n\x03'
    )

import unittest

from mq_filter.parse import apis
from mq_filter.parse import detect
from mq_filter.parse import dlnk
from mq_filter.parse import extract_payload_from_mq
from mq_filter.parse import flight_plan
from mq_filter.parse import simple

class TestParse(unittest.TestCase):

    def check_file(self, fn, expect_parser, expect_airline):
        with open(fn) as file:
            content = file.read()
            parser = detect(content)
            self.assertIs(parser, expect_parser)
            data = parser(content)
            self.assertEqual(data['airline_code'], expect_airline)

    def test_parse_apis(self):
        self.check_file('test/APIS 8C 1.txt', apis, '8C')
        self.check_file('test/APIS 8C 2.txt', apis, '8C')
        self.check_file('test/APIS Sample 8C 2.txt', apis, '8C')
        self.check_file('test/APIS Sample 8C.txt', apis, '8C')
        self.check_file('test/APIS Sample GB 2.txt', apis, 'GB')
        self.check_file('test/APIS Sample GB.txt', apis, 'GB')
        self.check_file('test/APIS GB.txt', apis, 'GB')

    def test_parse_flight_plan(self):
        self.check_file('test/Flight PLan 8C.txt', flight_plan, 'ATN')
        self.check_file('test/Flight Plan GB correct.txt', flight_plan, 'ABX')

    def test_parse_mv(self):
        self.check_file('test/MVA ATN.txt', simple, 'ATN')
        self.check_file('test/MVT GB.txt', simple, 'GB')

class TestExtract(unittest.TestCase):

    def test_extract_payload(self):
        # Test weird RFH messages get parsed to extract the plain text message.
        message = b"RFH \x00\x00\x00\x02\x00\x00\x01P\x00\x00\x01\x11\x00\x00\x04\xb8MQSTR   \x00\x00\x00\x00\x00\x00\x04\xb8\x00\x00\x00 <mcd><Msd>jms_text</Msd></mcd>  \x00\x00\x00X<jms><Dst>queue:///ISB.STAGSMX.SND.ARINC</Dst><Tms>1770591522997</Tms><Dlv>2</Dlv></jms>\x00\x00\x00\xa8<usr><breadcrumbId>125B06B71564E10-0000000000000F4C</breadcrumbId><CamelJmsDeliveryMode dt='i4'>2</CamelJmsDeliveryMode><IOCC_TLX_ID>MRS144594901</IOCC_TLX_ID></usr>   \r\n\x01QU ASIKORR\r\n.ATSGOPS 082258\r\n\x02MVA\r\nATN530/08.N751CX.ANU\r\nAD2229/2258 EA0555 ASI\r\n\x03"
        payload = extract_payload_from_mq(message)
        self.assertEqual(payload, '\r\n\x01QU ASIKORR\r\n.ATSGOPS 082258\r\n\x02MVA\r\nATN530/08.N751CX.ANU\r\nAD2229/2258 EA0555 ASI\r\n\x03')

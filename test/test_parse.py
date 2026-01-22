import unittest

from mq_filter.parse import apis
from mq_filter.parse import detect
from mq_filter.parse import dlnk
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

import argparse
import re
import string

class ParseError(Exception):
    pass


airline_code_pattern = r'(?<airline_code>8C|GB|ABX|ATN)'

two_letter_airline_codes = [
    '8C',
    'GB',
]

three_letter_airline_codes = [
    'ABX',
    'ATN',
]

class FlightPlanParser:

    def __init__(self, aftn_address):
        # Anticipating need to change this constant for queue migration.
        self.aftn_address = aftn_address

    def detect(self, text):
        lines = printable_splitlines(text)
        # Ours for line 5 starts with...
        if len(lines) > 3:
            if lines[4].startswith('(FPL'):
                return self

    def __call__(self, text):
        data = {}
        lines = printable_splitlines(text)

        match = re.match(r'^\(FPL-(?P<airline_code>ATN|ABX)', lines[4])
        if match:
            return match.groupdict()


class APISParser:

    def __init__(self, source_address):
        self.source_address = source_address

    def detect(self, line2):
        if re.match(self.source_address, line2):
            return self

    def __call__(self, text):
        lines = printable_splitlines(text)

        # last two characters in first part of line two split on whitespace
        data = {
            'airline_code': lines[1].split()[0][-2:]
        }
        return data


flight_plan = FlightPlanParser('ATLXRXA')
apis = APISParser(r'\.ILNDD(GB|8C)')

def printable_splitlines(text):
    lines = [''.join([char for char in line if char in string.printable]) for line in text.splitlines() ]
    return lines

def dlnk(text):
    # Format 6 (APIS Crew) Line one
    # DLNKN1427A   GB  3110 19DEC2025MIA  CVG  GB     TEXT   111TEXT UPLINK                          PART 1 OF 1
    data = {}
    lines = [line.strip() for line in text.splitlines()]

    line_one_parts = lines[0].split()

    if not line_one_parts[0].startswith('DLNK'):
        raise ParseError('Line one does not start with DLNK: {lines[0]}')

    data['airline_code'] = line_one_parts[1]
    return data

def simple(text):
    # Parse simple messages with the format type code on one or two lines.
    data = {}
    lines = [line.strip() for line in text.splitlines()]

    qu_text, qu_data = lines[0].split()

    if qu_text != 'QU':
        raise ParseError('First Line does not start with "QU"')

    data['qu'] = qu_data

    # Third line is message format type
    data['format_type'] = lines[2]

    airline_line = 3
    if data['format_type'] == 'COR':
        # Add second format type and adjust which line has the airline
        data['format_type'] += ' ' + lines[3]
        airline_line = lines[4]
    else:
        airline_line = lines[3]

    if airline_line[:3] in three_letter_airline_codes:
        data['airline_code'] = airline_line[:3]
    elif airline_line[:2] in two_letter_airline_codes:
        data['airline_code'] = airline_line[:2]
    else:
        raise ParseError(f'Airline code not found: {lines[airline_line]}')

    return data

def detect(text):
    lines = printable_splitlines(text)

    qu_parts = lines[0].split()
    if len(qu_parts) == 2:
        qu_text, qu_data = qu_parts
        if qu_text != 'QU':
            raise ParseError('First Line does not start with "QU"')

        if lines[2] in ('MVA', 'MVT', 'COR', 'DIV'):
            return simple
        elif flight_plan.detect(text):
            return flight_plan
        elif apis.detect(lines[1]):
            return apis
    elif lines[0].startswith('DLNKYABCD'):
        return dlnk
    else:
        raise ParseError(f'Parser not detected {text}')

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('messagefile', nargs='+')
    args = parser.parse_args(argv)

    for fn in args.messagefile:
        print(fn)
        with open(fn) as src:
            content = src.read()
            parser = detect(content)
            data = parser(content)
            print(data)

if __name__ == '__main__':
    main()
